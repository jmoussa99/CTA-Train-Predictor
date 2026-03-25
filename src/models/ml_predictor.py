class RandomForestPredictor:
    """Placeholder for future Random Forest arrival predictor.

    Planned features:
    - Train on historical CTA arrival data (log API responses over time)
    - Features: time of day, day of week, weather, line, direction, delay flags
    - Target: actual arrival delta vs CTA predicted arrival
    """

    def predict(self, *args, **kwargs):
        raise NotImplementedError(
            "Random Forest predictor is not yet implemented. "
            "See TICKETS.md Ticket 8 for planned feature description."
        )
