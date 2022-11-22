"""
TODO docstring
"""
import numpy as np
from data_array import DataArray
from sklearn.linear_model import LinearRegression
from scipy.signal import firwin, lfilter

GAS_DOWN = 20
EGG_BUFFER_DURATION = 35
MED_WIN = 250


def fir_bandpass_filter(data, lowcut, highcut, sampling_rate, order=5):
    """
    TODO docstring
    """
    fir_filter = firwin(order + 1, [lowcut, highcut], pass_zero=False, fs=sampling_rate)
    return lfilter(fir_filter, 1.0, data)


def median_filter(data, start_from_end, window_rad):
    """
    TODO docstring
    """
    start_index = len(data) - start_from_end
    if start_index < 0:
        start_index = 0

    returned_data = []
    for i in range(start_index, len(data)):
        start = max(0, i - window_rad)
        end = min(len(data), i + window_rad + 1)
        returned_data.append(np.median(data[start:end]))

    return returned_data


def egg_feedback(biofeedback):
    """
    TODO docstring
    """
    if biofeedback.state == "egg":
        down_sr = biofeedback.sampling_rate / GAS_DOWN
        len_buffer = int(EGG_BUFFER_DURATION * down_sr)
        buffer = DataArray(len_buffer, down=GAS_DOWN)
        med_buffer = DataArray(len_buffer)
        filter_buffer = DataArray(len_buffer)
        time_abscissa = np.array([x / down_sr for x in range(len_buffer)])
        num_smp, num_evt = biofeedback.ft_egg.wait(
            biofeedback.header_egg.nSamples, biofeedback.header_egg.nEvents, 500
        )
        while biofeedback.recording:
            new_smp, new_evt = biofeedback.ft_egg.wait(num_smp, num_evt, 500)
            if new_smp == num_smp:
                continue
            data_sample = biofeedback.ft_egg.getData([num_smp, new_smp - 1]).T
            egg = data_sample[biofeedback.egg_pos]
            down_data = buffer.add_data(egg)
            med_filtered = median_filter(buffer, MED_WIN + len(down_data), MED_WIN)
            med_buffer.add_data(med_filtered)
            filtered = fir_bandpass_filter(
                med_buffer,
                biofeedback.egg_freq - biofeedback.EGG_WIN,
                biofeedback.egg_freq + biofeedback.EGG_WIN,
                down_sr,
                1000,
            )
            filter_buffer.add_data(filtered[-len(down_data) :])
            if filter_buffer.full():
                if not biofeedback.audio_on:
                    biofeedback.audio_on = True
                model = LinearRegression().fit(
                    time_abscissa.reshape(-1, 1), filter_buffer
                )
                regre = time_abscissa * model.coef_ + model.intercept_
                mean = np.mean(filter_buffer)
                clean = filter_buffer - regre + mean
                modulation = (
                    np.mean(clean[len(clean) - len(down_data) :]) - min(clean)
                ) / (max(clean) - min(clean))
                biofeedback.sound_mod[0] = modulation

            num_smp = new_smp
            num_evt = new_evt
