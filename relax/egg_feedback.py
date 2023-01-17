"""
TODO docstring
"""
import numpy as np
from relax.data_array import DataArray
from sklearn.linear_model import LinearRegression
from scipy.signal import firwin, lfilter, hilbert
import time

GAS_DOWN = 30
EGG_BUFFER_DURATION = 45
MED_WIN = 100
EGG_WIN = 0.015
FIR_ORDER = 2000

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


def egg_modulation(egg,buffer,med_buffer,filter_buffer,time_abscissa,down_sr,egg_freq,last_mod,dt,dict_,save):
    """
    TODO docstring
    """

    # Down sample
    down_data = buffer.add_data(egg)

    # Median filtering
    med_filtered = median_filter(buffer, MED_WIN + len(down_data), MED_WIN)
    data_to_add = med_filtered[len(med_filtered)-len(down_data):]
    data_modified = med_filtered[:len(med_filtered)-len(down_data)]
    med_buffer[len(med_buffer)-len(data_modified):] = data_modified
    med_buffer.add_data(data_to_add)

    #Removing trend
    model_med = LinearRegression().fit(
        time_abscissa[:len(med_buffer)].reshape(-1, 1), med_buffer
    )
    regre_med = time_abscissa[:len(med_buffer)] * model_med.coef_ + model_med.intercept_
    clean_med = med_buffer - regre_med

    #Filtering
    filtered = fir_bandpass_filter(
        clean_med,
        egg_freq - EGG_WIN,
        egg_freq + EGG_WIN,
        down_sr,
        FIR_ORDER,
    )

    if len(filter_buffer) < filter_buffer.max_len and len(filter_buffer) + len(down_data) >= filter_buffer.max_len:
        filter_buffer[filter_buffer.max_len:] = filtered
    else:
        filter_buffer.add_data(filtered[-len(down_data) :])

    if filter_buffer.full():
        
        modulation = (
            np.mean(filter_buffer[len(filter_buffer) - len(down_data) :]) - min(filter_buffer)
        ) / (max(filter_buffer) - min(filter_buffer))
        
        if last_mod != -1.0:
            max_mod = last_mod + (2*np.pi*(egg_freq+EGG_WIN)*dt)
            min_mod = last_mod - (2*np.pi*(egg_freq+EGG_WIN)*dt)
            modulation = min(modulation,max_mod)
            modulation = max(modulation,min_mod)
        if save:
            dict_["buffer"].append(np.array(buffer).tolist())
            dict_["med_buffer"].append(np.array(med_buffer).tolist())
            dict_["regre_med"].append(np.array(regre_med).tolist())
            dict_["clean_med"].append(np.array(clean_med).tolist())
            dict_["filtered"].append(filtered.tolist())
            dict_["filter_buffer"].append(np.array(filter_buffer).tolist())
        return modulation
    else:
        return -1.0

def egg_feedback(biofeedback,test=False):
    """
    TODO docstring
    """
    print("Egg thread started")
    if biofeedback.state == "egg":
        last_mod = -1.0
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

            # Downsampling
            down_data = buffer.add_data(egg)

            if len(down_data) > 0 :

                # Median filter
                med_filtered = median_filter(buffer, MED_WIN + len(down_data), MED_WIN)
                data_to_add = med_filtered[len(med_filtered)-len(down_data):]
                data_modified = med_filtered[:len(med_filtered)-len(down_data)]
                med_buffer[len(med_buffer)-len(data_modified):] = data_modified
                med_buffer.add_data(data_to_add)

                #Removing trend
                model_med = LinearRegression().fit(
                    time_abscissa[:len(med_buffer)].reshape(-1, 1), med_buffer
                )
                regre_med = time_abscissa[:len(med_buffer)] * model_med.coef_ + model_med.intercept_
                clean_med = med_buffer - regre_med

                #Filtering
                filtered = fir_bandpass_filter(
                    clean_med,
                    biofeedback.egg_freq - EGG_WIN,
                    biofeedback.egg_freq + EGG_WIN,
                    down_sr,
                    FIR_ORDER,
                )

                # Filter_buffer init at start
                if (len(filter_buffer) < filter_buffer.max_len and 
                    len(filter_buffer) + len(down_data) >= filter_buffer.max_len):
                    filter_buffer[filter_buffer.max_len:] = filtered
                else:
                    filter_buffer.add_data(filtered[-len(down_data) :])

                if filter_buffer.full():
                    if not biofeedback.audio_on:
                        biofeedback.audio_on = True

                    #Modulation computation
                    modulation = (np.mean(filter_buffer[len(filter_buffer) - len(down_data) :])
                                  - min(filter_buffer)) / (max(filter_buffer) - min(filter_buffer))

                    #Cap the modulation change
                    if last_mod != -1.0:
                        change = (2*np.pi*(biofeedback.egg_freq+EGG_WIN)*
                              len(egg)*biofeedback.sampling_rate)
                        max_mod = last_mod + change
                        min_mod = last_mod - change
                        modulation = min(modulation,max_mod)
                        modulation = max(modulation,min_mod)
                    last_mod = modulation

                    #Update egg volume
                    biofeedback.sound_mod[0] = modulation

            num_smp = new_smp
            num_evt = new_evt
        print("Egg thread finished")
    elif not test:
        last_index = 0
        mock_time = biofeedback.mock_time
        mock_egg = biofeedback.mock_egg

        while not biofeedback.audio_on:
            time.sleep(0.1)

        while biofeedback.recording:
            in_mock_time = time.time() - biofeedback.audio_start
            for i in range(last_index,len(mock_time)-1):
                if mock_time[i] <= in_mock_time and mock_time[i+1] > in_mock_time:
                    last_index = i
                    break
            biofeedback.sound_mod[0] = mock_egg[last_index]
            time.sleep(0.01)
        print("Egg thread finished")
