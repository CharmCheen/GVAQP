from garc_eval.accelerated_event_query import ModelRelativeUnitLabel


def unit(
    index: int,
    outcome: str,
    *,
    video_id: str = "V0",
    evidence: str | None = None,
    confidence: str | None = None,
) -> ModelRelativeUnitLabel:
    return ModelRelativeUnitLabel(
        unit_id=f"{video_id}_u{index:04d}",
        query_id="Q_DRIVER_RESPONSE_V1",
        video_id=video_id,
        start_time=10.0 * index,
        end_time=10.0 * (index + 1),
        outcome=outcome,
        evidence=evidence,
        confidence=confidence,
    )
