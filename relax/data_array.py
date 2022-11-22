"""
TODO docstring
"""
import numpy as np


class DataArray(list):
    """
    TODO docstring
    """

    def __init__(self, max_len, down=None):
        super().__init__()
        self.max_len = max_len
        self.down = down
        self.sub_buffer = []

    def add_data(self, data_sample):
        """
        TODO docstring
        """
        if self.down:
            down_data_sample = []
            self.sub_buffer = self.sub_buffer + list(data_sample)
            while len(self.sub_buffer) >= self.down:
                down_data_sample.append(np.mean(self.sub_buffer[0 : self.down]))
                del self.sub_buffer[0 : self.down]
            data_sample = down_data_sample

        overload = (len(self) + len(data_sample)) - self.max_len
        if overload > 0:
            del self[0:overload]
        self += data_sample
        return data_sample

    def prop(self, value):
        """
        TODO docstring
        """
        return (value - min(self)) / (max(self) - min(self))

    def full(self):
        """
        TODO docstring
        """
        return len(self) == self.max_len
