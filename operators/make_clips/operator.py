from abc import ABC, abstractmethod
from ..base.operator import Operator

class MakeClips(Operator):

    @abstractmethod
    def apply(self, *args, **kwargs):
        return super().apply(*args, **kwargs)

