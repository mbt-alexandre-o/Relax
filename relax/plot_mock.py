"""
Module to plot the mock volume modulation of a subject
"""
import json
from datetime import date
from pathlib import Path

import click
import matplotlib.pyplot as plt
from create_mock_soundscapes import SAMP_FREQ


def plot_mod(dict_):
    """
    Function that plot the different mock modulation shuffled

    Parameters
    ----------
    dict_: Dictionary
        dictionary containing the volume modulation
    """
    sub_key = ["or", "1", "2", "3", "4"]
    for key in ["ecg_", "egg_", "resp_"]:
        fig, axs = plt.subplots(5, 1, sharex=True)
        fig.subplots_adjust(hspace=0)
        axs[-1].set_xlabel("time (s)")
        for i, sub in enumerate(sub_key):
            axs[i].plot(
                [x / SAMP_FREQ for x in range(len(dict_[key + sub]))], dict_[key + sub]
            )
        plt.show()


@click.command()
@click.option("--subject_id", prompt="Subject id")
@click.option("--day", type=str, prompt="Date", default=str(date.today()))
def plot_mock_soundscapes(subject_id, day):
    """
    Click interface to plot mock volume modulation of a given subject
    
    Parameters
    ----------
    subject_id: String
        unique string id of the subject. It should be the same as the one
        used for recording the baseline.
    day: String
        Day of the desire resting state mock computation.
    """
    record_folder = Path(__file__).parent / "../records/"
    with open(
        str(record_folder) + f"/mock-modulation_{day}_{subject_id}.json", "r"
    ) as file:
        data = json.load(file)
    plot_mod(data)


if __name__ == "__main__":
    plot_mock_soundscapes()
