"""
TODO docstring
"""
import json
from datetime import date
from pathlib import Path

import click
import matplotlib.pyplot as plt


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

@click.command()
@click.option("--subject_id", prompt="Subject id")
@click.option("--day",type = str, prompt="Date", default=str(date.today()))
def plot_mock_soundscapes(subject_id,day):
    """
    TODO docstring
    """
    record_folder = Path(__file__).parent / "../records/"
    with open(str(record_folder)+f"/mock-modulation_{day}_{subject_id}.json","r") as file:
        data = json.load(file)
    plot_mod(data)

if __name__ == "__main__":
    plot_mock_soundscapes()
