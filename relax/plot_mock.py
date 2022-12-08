"""
TODO docstring
"""
import json
import os
from pathlib import Path

import click
from create_mock_soundscapes import plot_mod


@click.command()
@click.option("--subject_id", prompt="Subject id")
@click.option("--date", prompt="Date")
def plot_mock(subject_id,date):
    """
    TODO docstring
    """
    record_folder = Path(__file__).parent / "../records/"
    file_list = os.listdir(record_folder)
    expected_file = f"mock-modulation_{date}_{subject_id}.json"
    if expected_file in file_list:
        with open(str(record_folder/expected_file),"r") as file:
            data = json.load(file)
        plot_mod(data["ecg_mod"],data["resp_mod"],data["egg_mod"])
        
if __name__ == "__main__":
    plot_mock()
    