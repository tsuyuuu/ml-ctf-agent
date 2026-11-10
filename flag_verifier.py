
class FlagVerifier:
    """
    Trusted-controller interface for flag verification.

    The actual course verifier must be connected separately.
    Expected flags must never enter the solver container,
    agent prompt, or model-visible tool results.
    """

    def __init__(self, verify_callback=None):
        self.verify_callback = verify_callback
        self.submissions = []

    def verify(self, candidate):
        if not isinstance(candidate, str) or not candidate.strip():
            return {
                "verified": False,
                "error": "Invalid candidate"
            }

        if self.verify_callback is None:
            return {
                "verified": False,
                "error": "Private evaluator not configured"
            }

        verified = self.verify_callback(candidate)

        if not isinstance(verified, bool):
            raise TypeError("Verifier must return a boolean")

        self.submissions.append({
            "candidate": candidate,
            "verified": verified
        })

        return {"verified": verified}
