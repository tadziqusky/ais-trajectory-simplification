# Introduction 
This repository contains implementations of three trajectory simplification algorithms: Down-sampling, Douglas-Peucker, and O-EPP. Those algorithms were used to measure the influence of trajectory simplification on ship CO2 emission estimation.

# Getting Started
First, required dependencies need to be installed.

```
pip install -r requirements.txt
```

Next, you can run notebooks to clean raw AIS data and apply simplification:

- pynotebooks/01. clean_input - it reads sample trajectory from *data/raw/sample_ship.csv* and apply cleaning function and downsamples to every 10 minutes. Result is stored in data/processed/cleaned.csv
- pynotebooks/02. simplify_trajectories - It applies simplification algorithms and put results into data/processed folder

Data can be found in *data* folder:

- data/raw - contains sample input
- data/processed - contains results from running notebooks

data/raw/sample_ship.csv contains historical AIS data for one ship, taken from the Danish Maritime Authority website (https://dma.dk/safety-at-sea/navigational-information/ais-data).

