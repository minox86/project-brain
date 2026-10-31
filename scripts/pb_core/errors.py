"""Toolkit exceptions. Every PbError maps to exit code 2."""


class PbError(Exception):
    def __init__(self, message, payload=None):
        super().__init__(message)
        self.payload = payload


class UsageError(PbError):
    pass


class FrontmatterError(PbError):
    pass


class NotInBrain(PbError):
    pass


class GitError(PbError):
    pass
