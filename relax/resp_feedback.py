"""
TODO docstring
"""
from relax.data_array import DataArray
import numpy as np

RESP_BUFFER_DURATION = 10


def resp_feedback(bfb):
    """
    TODO docstring
    """
    if bfb.state == "resp":
        buffer = DataArray(RESP_BUFFER_DURATION * bfb.sampling_rate)
        num_smp, num_evt = bfb.ft_resp.wait(
            bfb.header_resp.nSamples, bfb.header_resp.nEvents, 500
        )
        while bfb.recording:
            new_smp, new_evt = bfb.ft_resp.wait(num_smp, num_evt, 500)
            if new_smp == num_smp:
                continue
            data_sample = np.array(bfb.ft_resp.getData([num_smp, new_smp - 1])).T
            resp = data_sample[bfb.resp_pos]
            buffer.add_data(resp)
            if buffer.full():
                if not bfb.audio_on:
                    bfb.audio_on = True
                modulation = buffer.prop(np.mean(resp))
                bfb.sound_mod[2] = modulation

            num_smp = new_smp
            num_evt = new_evt
