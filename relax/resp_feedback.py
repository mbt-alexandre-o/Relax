"""
TODO docstring
"""
from relax.data_array import DataArray
import numpy as np
import time

RESP_BUFFER_DURATION = 10


def resp_modulation(resp,buffer):
    """
    TODO docstring
    """
    buffer.add_data(resp)
    if buffer.full():
        return buffer.prop(np.mean(resp))
    return 0.0

def resp_feedback(bfb,test=False):
    """
    TODO docstring
    """
    print("Resp thread started")
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
        print("Resp thread finished")
    elif not test:
        last_index = 0
        mock_time = bfb.mock_time
        mock_resp = bfb.mock_resp

        while not bfb.audio_on:
            time.sleep(0.1)

        while bfb.recording:
            in_mock_time = time.time() - bfb.audio_start
            for i in range(last_index,len(mock_time)-1):
                if mock_time[i] <= in_mock_time and mock_time[i+1] > in_mock_time:
                    last_index = i
                    break
            bfb.sound_mod[2] = mock_resp[last_index]
            time.sleep(0.01)
        print("Resp thread finished")
