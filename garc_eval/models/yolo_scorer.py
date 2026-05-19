"""YOLO-based frame scorer using ultralytics."""

from pathlib import Path

from .base import FrameScore, FrameScorer


class YOLOFrameScorer(FrameScorer):
    """Score frames using a YOLO model from ultralytics.

    For each frame, finds all boxes of `target_class` and returns:
    - score = highest confidence among matched boxes
    - count = number of matched boxes
    - max_conf = same as score (single-class)
    If no detection: score=0.0, count=0.
    """

    def __init__(
        self,
        model_path: str,
        target_class: int | str = 0,
        device: str = "cpu",
        batch_size: int = 32,
        conf_threshold: float = 0.25,
    ):
        try:
            from ultralytics import YOLO
        except ImportError:
            raise ImportError(
                "ultralytics is not installed. "
                "Install it on the server with: pip install ultralytics"
            )

        resolved = str(Path(model_path).expanduser())
        if not Path(resolved).exists():
            raise FileNotFoundError(f"Model file not found: {resolved}")

        self.model = YOLO(resolved)
        self.model.to(device)
        self.target_class = target_class
        self.device = device
        self.batch_size = batch_size
        self.conf_threshold = conf_threshold

    def _resolve_class_id(self, names: dict) -> int:
        """Resolve target_class to an integer class id."""
        if isinstance(self.target_class, int):
            return self.target_class
        # name string -> id
        for cid, cname in names.items():
            if cname == self.target_class:
                return cid
        raise ValueError(
            f"target_class '{self.target_class}' not found in model classes: {names}"
        )

    def score_frames(self, frame_rows: list[dict]) -> list[FrameScore]:
        paths = [r["image_path"] for r in frame_rows]
        ids = [r["id"] for r in frame_rows]
        results: list[FrameScore] = []

        for batch_start in range(0, len(paths), self.batch_size):
            batch_paths = paths[batch_start : batch_start + self.batch_size]
            batch_ids = ids[batch_start : batch_start + self.batch_size]

            preds = self.model(
                batch_paths,
                conf=self.conf_threshold,
                verbose=False,
            )

            class_names = preds[0].names if preds else {}
            class_id = self._resolve_class_id(class_names)

            for fid, pred in zip(batch_ids, preds):
                boxes = pred.boxes
                if boxes is None or len(boxes) == 0:
                    results.append(FrameScore(id=fid, score=0.0, count=0, max_conf=0.0))
                    continue

                cls_ids = boxes.cls.cpu().numpy().astype(int)
                confs = boxes.conf.cpu().numpy()
                mask = cls_ids == class_id
                matched_confs = confs[mask]

                if len(matched_confs) == 0:
                    results.append(FrameScore(id=fid, score=0.0, count=0, max_conf=0.0))
                else:
                    max_c = float(matched_confs.max())
                    results.append(
                        FrameScore(
                            id=fid,
                            score=max_c,
                            count=int(len(matched_confs)),
                            max_conf=max_c,
                        )
                    )

        return results
