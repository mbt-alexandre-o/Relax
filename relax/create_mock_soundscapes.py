"""
TODO docstring
"""
import click
from pathlib import Path
import os
from datetime import date
import mne
import numpy as np
import matplotlib.pyplot as plt
import json
from random import randint

from alive_progress import alive_bar
from relax.egg_feedback import egg_modulation, GAS_DOWN, EGG_BUFFER_DURATION
from relax.ecg_feedback import ecg_modulation, ECG_BUFFER_DURATION
from relax.resp_feedback import resp_modulation, RESP_BUFFER_DURATION
from relax.data_array import DataArray

SAMP_FREQ = 64

def get_half_crossing(data,padding = 128):
    """
    TODO docstring
    """
    crossing_points = []
    for i in range(padding,len(data)):
        if data[i-1]>0.5 and data[i]<= 0.5 and np.mean(data[i-padding:i])>0.5:
            crossing_points.append(i)
    return crossing_points


def get_recomposed_mock(data,n_recomposed,padding = 128):
    """
    TODO docstring
    """
    recomposed_mock = []
    crossing_points = get_half_crossing(data,padding)
    pstart = crossing_points[0]
    pend = crossing_points[-1]
    for _ in range(n_recomposed):
        pmid = crossing_points[randint(2,len(crossing_points)-2)]
        recomposed = data[:pstart]+data[pmid:pend]+data[pstart:pmid]+data[pend:]
        recomposed_mock.append(recomposed)
    return recomposed_mock


def add_recomposed_mock_to_dict(dict_):
    for key in ["ecg_or","egg_or","resp_or"]:
        data = dict_[key]
        if key == "ecg_or":
            padding = 1
        else:
            padding = 128
        recomposed_mock = get_recomposed_mock(data,4,padding)
        for i in range(len(recomposed_mock)):
            dict_[key.replace("_or","_"+str(i+1))] = recomposed_mock[i]


def plot_mod(dict_):
    """
    TODO docstring
    """
    sub_key = ["or","1","2","3","4"]
    time = dict_["time"]
    for key in ["ecg_","egg_","resp_"]: 
        fig, axs = plt.subplots(5, 1, sharex=True)
        fig.subplots_adjust(hspace=0)
        axs[-1].set_xlabel("time (s)")
        for i,sub in enumerate(sub_key):
            axs[i].plot([x/64 for x in range(len(dict_[key+sub]))], dict_[key+sub])
        plt.show()

def get_resp_modulation(sfreq,resp_data):
    """
    TODO docstring
    """
    mod_array = []
    samp_size = int(sfreq/SAMP_FREQ)
    buffer = DataArray(RESP_BUFFER_DURATION * sfreq)
    index_list = np.arange(0,len(resp_data),samp_size)
    with alive_bar(len(index_list)) as bar:
        for index in index_list:
            resp = resp_data[index:index+samp_size]
            if len(resp)>0:
                mod = resp_modulation(resp,buffer)
                if mod != -1.0:
                    mod_array.append(mod)
            bar()
    return mod_array


def get_egg_modulation(sfreq, egg_data, egg_freq):
    """
    TODO docstring
    """
    mod_array = []
    samp_size = int(sfreq/SAMP_FREQ)
    down_sr = sfreq / GAS_DOWN
    len_buffer = int(EGG_BUFFER_DURATION * down_sr)
    buffer = DataArray(len_buffer, down=GAS_DOWN)
    med_buffer = DataArray(len_buffer)
    filter_buffer = DataArray(len_buffer)
    time_abscissa = np.array([x / down_sr for x in range(len_buffer)])
    index_list = np.arange(0,len(egg_data),samp_size)
    with alive_bar(len(index_list)) as bar:
        for index in index_list:
            egg = egg_data[index:index+samp_size]
            if len(egg)>0:
                mod = egg_modulation(egg,buffer,med_buffer,filter_buffer,time_abscissa,down_sr,egg_freq)
                if mod != -1.0:
                    mod_array.append(mod)
            bar()
    return mod_array

def get_ecg_modulation(sfreq,ecg_data):
    """
    TODO docstring
    """
    heart_beat = []
    samp_size = int(sfreq/SAMP_FREQ)
    last_time = 0
    last_ecg_point = 0
    buffer = DataArray(ECG_BUFFER_DURATION * sfreq)
    index_list = np.arange(0,len(ecg_data),samp_size)
    with alive_bar(len(index_list)) as bar:
        for index in index_list:
            ecg = ecg_data[index:index+samp_size]
            if len(ecg)>0:
                array = ecg_modulation(ecg,last_ecg_point,buffer,last_time,index/sfreq)
                last_ecg_point = array[0]
                if len(array)==2:
                    last_time = array[1]
                    heart_beat.append(1)
                else:
                    heart_beat.append(0)
            bar()
    return heart_beat

@click.command()
@click.option("--subject_id", prompt="Subject id")
@click.option("--egg_electrod",type = int, prompt="Egg electrod")
@click.option("--egg_freq",type = float, prompt="Egg freq")
@click.option("--day",type = str, prompt="Date", default=str(date.today()))
def create_mock_soundscapes(subject_id,egg_electrod,egg_freq,day):
    """
    TODO docstring
    """
    record_folder = Path(__file__).parent / "../records/"
    file_list = os.listdir(record_folder)
    expected_file = f"RS_{day}_{subject_id}.fif"
    if expected_file in file_list:
        print("Resting state file founded.")
        raw = mne.io.Raw(str(record_folder/expected_file))
        sfreq = raw.info['sfreq']
        resp_data = raw.get_data(["Resp"])[0]
        ecg_data = raw.get_data(["EGG2ECG"])[0] - raw.get_data(["EGG8ECG"])[0]
        egg_data = raw.get_data([f"EGG{egg_electrod}"])[0]
        ecg_mod = get_ecg_modulation(sfreq,ecg_data)
        resp_mod = get_resp_modulation(sfreq,resp_data)
        egg_mod = get_egg_modulation(sfreq,egg_data,egg_freq)
        dict_ = {
            "ecg_or":ecg_mod,
            "resp_or":resp_mod,
            "egg_or":egg_mod,
            "time":[x/SAMP_FREQ for x in range(len(ecg_mod))]
        }
        add_recomposed_mock_to_dict(dict_)
        save_file = f"mock-modulation_{day}_{subject_id}.json"
        with open(str(record_folder/save_file),"w") as f:
            json.dump(dict_,f)
        plot_mod(dict_)
    else:
        print(f"{expected_file} was not found.")

if __name__ == "__main__":
    create_mock_soundscapes()
