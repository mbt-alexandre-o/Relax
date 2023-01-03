"""
TODO docstring
"""
import json
from pathlib import Path

from datetime import date
import click
from create_mock_soundscapes import plot_mod

@click.command()
@click.option("--subject_id", prompt="Subject id")
@click.option("--day",type = str, prompt="Date", default=str(date.today()))
def create_mock_soundscapes(subject_id,day):
    """
    TODO docstring
    """
    record_folder = Path(__file__).parent / "../records/"
    with open(str(record_folder)+f"/mock-modulation_{day}_{subject_id}.json","r") as file:
        data = json.load(file)

    plot_mod(data)

if __name__ == "__main__":
    create_mock_soundscapes()
