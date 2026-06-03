import cv2
import uuid
import json
import os
import argparse
from datetime import datetime, timezone, timedelta
from ultralytics import YOLO

# ─── Camera roles ───────────────────────────────────────────
# NEW — spaces in names + CAM4 is now floor not empty
CAMERA_ROLES = {
    "CAM 1": {"role": "floor",   "camera_id": "CAM_FLOOR_01",   "zone": "MAIN_FLOOR"},
    "CAM 2": {"role": "floor",   "camera_id": "CAM_FLOOR_02",   "zone": "MAIN_FLOOR"},
    "CAM 3": {"role": "entry",   "camera_id": "CAM_ENTRY_03",   "zone": None},
    "CAM 4": {"role": "floor",   "camera_id": "CAM_FLOOR_04",   "zone": "MAIN_FLOOR"},
    "CAM 5": {"role": "billing", "camera_id": "CAM_BILLING_05", "zone": "BILLING_AREA"},
}

STORE_ID   = "STORE_BLR_002"
BASE_TIME = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
FRAME_H    = 1080
ENTRY_LINE = FRAME_H // 2   # horizontal line across frame for entry/exit
CONF_THRESHOLD = 0.35       # ignore detections below this confidence

# ─── Globals shared across cameras ──────────────────────────
# visitor_id registry:  track_id → visitor_id
track_registry = {}

# re-entry registry:    visitor_id → last exit timestamp
exit_registry  = {}

# dwell tracker:        visitor_id → {zone, first_seen_frame, last_dwell_emitted_frame}
dwell_tracker  = {}

# direction tracker:    track_id → {y, crossed, side}
direction_tracker = {}

# session sequence:     visitor_id → int
session_seq = {}


def frame_to_timestamp(frame_num: int, fps: float) -> str:
    offset = timedelta(seconds=frame_num / fps)
    return (BASE_TIME + offset).isoformat().replace("+00:00", "Z")


def get_visitor_id(track_id: int) -> str:
    if track_id not in track_registry:
        track_registry[track_id] = "VIS_" + uuid.uuid4().hex[:6].upper()
    return track_registry[track_id]


def next_seq(visitor_id: str) -> int:
    session_seq[visitor_id] = session_seq.get(visitor_id, 0) + 1
    return session_seq[visitor_id]


def build_event(
    visitor_id, event_type, timestamp, conf,
    camera_id, zone_id=None, is_staff=False,
    dwell_ms=0, queue_depth=None
) -> dict:
    return {
        "event_id":   str(uuid.uuid4()),
        "store_id":   STORE_ID,
        "camera_id":  camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp":  timestamp,
        "zone_id":    zone_id,
        "dwell_ms":   dwell_ms,
        "is_staff":   is_staff,
        "confidence": round(float(conf), 3),
        "metadata": {
            "queue_depth": queue_depth,
            "sku_zone":    zone_id,
            "session_seq": next_seq(visitor_id)
        }
    }


def detect_staff(track_id: int, zone_history: dict) -> bool:
    """
    Simple staff heuristic:
    A person seen in 3+ different zones is likely staff.
    """
    zones = zone_history.get(track_id, set())
    return len(zones) >= 3


def process_entry_camera(
    track_id, visitor_id, cy, frame_num,
    fps, camera_id, conf, events
):
    """
    CAM3 outside facing entrance.
    Any person detected = potential entry.
    Direction confirmed by vertical movement.
    """
    THRESHOLD = 30  # reduced threshold for outside cam
    timestamp = frame_to_timestamp(frame_num, fps)

    prev = direction_tracker.get(track_id)

    if prev is None:
        direction_tracker[track_id] = {
            "y": cy, "crossed": False,
            "side": "outside", "frame": frame_num
        }
        # emit ENTRY on first detection at entry cam
        last_exit = exit_registry.get(visitor_id)
        event_type = "REENTRY" if last_exit else "ENTRY"
        events.append(build_event(
            visitor_id, event_type, timestamp,
            conf, camera_id
        ))
        return

    prev_y  = prev["y"]
    crossed = prev["crossed"]

    if not crossed:
        if abs(cy - prev_y) > THRESHOLD:
            if cy > prev_y:
                # moving down = entering
                last_exit = exit_registry.get(visitor_id)
                event_type = "REENTRY" if last_exit else "ENTRY"
                events.append(build_event(
                    visitor_id, event_type, timestamp,
                    conf, camera_id
                ))
            else:
                # moving up = exiting
                events.append(build_event(
                    visitor_id, "EXIT", timestamp,
                    conf, camera_id
                ))
                exit_registry[visitor_id] = timestamp

            direction_tracker[track_id]["crossed"] = True

    direction_tracker[track_id]["y"] = cy


def process_floor_camera(
    track_id, visitor_id, frame_num,
    fps, camera_id, zone, conf,
    events, zone_history, is_staff
):
    """
    CAM1 and CAM2 — main floor.
    Emit ZONE_ENTER on first appearance.
    Emit ZONE_DWELL every 30 seconds of continuous presence.
    """
    DWELL_INTERVAL_FRAMES = 30 * 15  # 30 seconds × 15fps

    timestamp = frame_to_timestamp(frame_num, fps)
    key = (track_id, zone)

    # track zone history for staff detection
    if track_id not in zone_history:
        zone_history[track_id] = set()
    zone_history[track_id].add(zone)

    if key not in dwell_tracker:
        # first time seen in this zone
        dwell_tracker[key] = {
            "first_frame":        frame_num,
            "last_dwell_frame":   frame_num,
            "zone_enter_emitted": False
        }

    info = dwell_tracker[key]

    # emit ZONE_ENTER once
    if not info["zone_enter_emitted"]:
        events.append(build_event(
            visitor_id, "ZONE_ENTER", timestamp,
            conf, camera_id, zone_id=zone, is_staff=is_staff
        ))
        info["zone_enter_emitted"] = True

    # emit ZONE_DWELL every 30 seconds
    frames_since_dwell = frame_num - info["last_dwell_frame"]
    if frames_since_dwell >= DWELL_INTERVAL_FRAMES:
        dwell_ms = int((frames_since_dwell / 15) * 1000)
        events.append(build_event(
            visitor_id, "ZONE_DWELL", timestamp,
            conf, camera_id, zone_id=zone,
            is_staff=is_staff, dwell_ms=dwell_ms
        ))
        info["last_dwell_frame"] = frame_num


def process_billing_camera(
    track_id, visitor_id, frame_num,
    fps, camera_id, conf, events,
    zone_history, is_staff, queue_depth
):
    """
    CAM5 — billing area.
    Track queue depth by counting people in frame.
    Emit BILLING_QUEUE_JOIN when queue > 0.
    """
    zone = "BILLING_AREA"
    timestamp = frame_to_timestamp(frame_num, fps)

    if track_id not in zone_history:
        zone_history[track_id] = set()
    zone_history[track_id].add(zone)

    key = (track_id, zone)
    if key not in dwell_tracker:
        dwell_tracker[key] = {
            "first_frame":        frame_num,
            "last_dwell_frame":   frame_num,
            "zone_enter_emitted": False
        }
        if queue_depth > 0:
            events.append(build_event(
                visitor_id, "BILLING_QUEUE_JOIN", timestamp,
                conf, camera_id, zone_id=zone,
                is_staff=is_staff, queue_depth=queue_depth
            ))
        else:
            events.append(build_event(
                visitor_id, "ZONE_ENTER", timestamp,
                conf, camera_id, zone_id=zone,
                is_staff=is_staff
            ))
        dwell_tracker[key]["zone_enter_emitted"] = True


def process_video(video_path: str, cam_name: str, output_path: str):
    config    = CAMERA_ROLES[cam_name]
    role      = config["role"]
    camera_id = config["camera_id"]
    zone      = config["zone"]

    if role == "empty":
        print(f"Skipping {cam_name} — no movement expected")
        return 0

    if not os.path.exists(video_path):
        print(f"ERROR: {video_path} not found — skipping")
        return 0

    print(f"\nProcessing {cam_name} ({role}) ...")
    model = YOLO("yolov8n.pt")

    cap    = cv2.VideoCapture(video_path)
    fps    = cap.get(cv2.CAP_PROP_FPS) or 15
    total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    events = []
    zone_history = {}   # track_id → set of zones seen

    frame_num = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # progress log every 500 frames
        if frame_num % 500 == 0:
            pct = round(frame_num / total * 100) if total else 0
            print(f"  {cam_name}: frame {frame_num}/{total} ({pct}%)")

        # run YOLOv8 tracking
        results = model.track(
            frame,
            persist=True,
            classes=[0],        # class 0 = person only
            conf=CONF_THRESHOLD,
            verbose=False
        )

        if results[0].boxes.id is None:
            frame_num += 1
            continue

        boxes      = results[0].boxes
        track_ids  = boxes.id.int().tolist()
        queue_depth = len(track_ids)   # number of people in billing frame

        for i, track_id in enumerate(track_ids):
            box        = boxes.xyxy[i].tolist()
            conf       = float(boxes.conf[i])
            cy         = (box[1] + box[3]) / 2
            visitor_id = get_visitor_id(track_id)
            is_staff   = detect_staff(track_id, zone_history)

            if role == "entry":
                process_entry_camera(
                    track_id, visitor_id, cy,
                    frame_num, fps, camera_id, conf, events
                )

            elif role == "floor":
                process_floor_camera(
                    track_id, visitor_id, frame_num,
                    fps, camera_id, zone, conf,
                    events, zone_history, is_staff
                )

            elif role == "billing":
                process_billing_camera(
                    track_id, visitor_id, frame_num,
                    fps, camera_id, conf, events,
                    zone_history, is_staff, queue_depth
                )

        frame_num += 1

    cap.release()

    # write events to output file
    with open(output_path, "a", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    print(f"  {cam_name}: done — {len(events)} events written")
    return len(events)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="./data")
    parser.add_argument("--output",   default="./events.jsonl")
    args = parser.parse_args()

    # clear output file
    open(args.output, "w").close()

    total_events = 0
    # NEW
    for cam_name in ["CAM 1", "CAM 2", "CAM 3", "CAM 4", "CAM 5"]:
        video_path = os.path.join(args.data_dir, f"{cam_name}.mp4")
        count = process_video(video_path, cam_name, args.output)
        total_events += count

    print(f"\nAll cameras done. Total events: {total_events}")
    print(f"Output written to: {args.output}")


if __name__ == "__main__":
    main()