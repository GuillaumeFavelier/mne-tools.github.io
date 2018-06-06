"""
===========================================================================
Visualising statistical significance thresholds on EEG data
===========================================================================

MNE-Python provides a range of tools for statistical hypothesis testing
and the visualisation of the results. Here, we show a few options for
exploratory and confirmatory tests - e.g., targeted t-tests, cluster-based
permutation approaches (here with Threshold-Free Cluster Enhancement);
and how to visualise the results.

The underlying data comes from [1]_; we contrast long vs. short words.
TFCE is described in [2]_.

References
----------
.. [1] Dufau, S., Grainger, J., Midgley, KJ., Holcomb, PJ. A thousand
   words are worth a picture: Snapshots of printed-word processing in an
   event-related potential megastudy. Psychological Science, 2015
.. [2] Smith and Nichols 2009, "Threshold-free cluster enhancement:
   addressing problems of smoothing, threshold dependence, and
   localisation in cluster inference", NeuroImage 44 (2009) 83-98.
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import ttest_ind

import mne
from mne.channels import find_ch_connectivity, make_1020_channel_selections
from mne.stats import spatio_temporal_cluster_test

np.random.seed(0)

# Load the data
path = mne.datasets.kiloword.data_path() + '/kword_metadata-epo.fif'
epochs = mne.read_epochs(path)
name = "NumberOfLetters"

# Split up the data by the median length in letters via the attached metadata
median_value = str(epochs.metadata[name].median())
long = epochs[name + " > " + median_value]
short = epochs[name + " < " + median_value]

#############################################################################
# If we have a specific point in space and time we wish to test, it can be
# convenient to convert the data into Pandas Dataframe format. In this case,
# the :class:`mne.Epochs` object has a convenient
# :meth:`mne.Epochs.to_data_frame` method, which returns a dataframe.
# This dataframe can then be queried for specific time windows and sensors.
# The extracted data can be submitted to standard statistical tests. Here,
# we conduct t-tests on the difference between long and short words.

time_windows = ((.2, .25), (.35, .45))
elecs = ["Fz", "Cz", "Pz"]

# display the EEG data in Pandas format (first 5 rows)
print(epochs.to_data_frame()[elecs].head())

report = "{elec}, time: {tmin}-{tmax} s; t({df})={t_val:.3f}, p={p:.3f}"
print("\nTargeted statistical test results:")
for (tmin, tmax) in time_windows:
    long_df = long.copy().crop(tmin, tmax).to_data_frame()
    short_df = short.copy().crop(tmin, tmax).to_data_frame()
    for elec in elecs:
        # extract data
        A = long_df[elec].groupby("condition").mean()
        B = short_df[elec].groupby("condition").mean()

        # conduct t test
        t, p = ttest_ind(A, B)

        # display results
        format_dict = dict(elec=elec, tmin=tmin, tmax=tmax,
                           df=len(epochs.events) - 2, t_val=t, p=p)
        print(report.format(**format_dict))

##############################################################################
# Absent specific hypotheses, we can also conduct an exploratory
# mass-univariate analysis at all sensors and time points. This requires
# correcting for multiple tests.
# MNE offers various methods for this; amongst them, cluster-based permutation
# methods allow deriving power from the spatio-temoral correlation structure
# of the data. Here, we use TFCE.

# Calculate statistical thresholds
con = find_ch_connectivity(epochs.info, "eeg")

# Extract data: transpose because the cluster test requires channels to be last
# In this case, inference is done over items. In the same manner, we could
# also conduct the test over, e.g., subjects.
X = [long.get_data().transpose(0, 2, 1),
     short.get_data().transpose(0, 2, 1)]
tfce = dict(start=.2, step=.2)

t_obs, clusters, cluster_pv, h0 = spatio_temporal_cluster_test(
    X, tfce, n_permutations=100)
significant_points = cluster_pv.reshape(t_obs.shape).T < .05
print(str(significant_points.sum()) + " points selected by TFCE ...")

##############################################################################
# The results of these mass univariate analyses can be visualised by plotting
# :class:`mne.Evoked` objects as images (via :class:`mne.Evoked.plot_image`)
# and masking points for significance.
# Here, we group channels by Regions of Interest to facilitate localising
# effects on the head.

# We need an evoked object to plot the image to be masked
evoked = mne.combine_evoked([long.average(), -short.average()],
                            weights='equal')  # calculate difference wave
time_unit = dict(time_unit="s")
evoked.plot_joint(title="Long vs. short words", ts_args=time_unit,
                  topomap_args=time_unit)  # show difference wave

# Create ROIs by checking channel labels
selections = make_1020_channel_selections(evoked.info, midline="12z")

# Visualize the results
fig, axes = plt.subplots(nrows=3, figsize=(8, 8))
vmax = np.abs(evoked.data).max() * 1e6

# Iterate over ROIs and axes
axes = axes.ravel().tolist()
for selection_name, ax in zip(sorted(selections.keys()), axes):
    picks = selections[selection_name]
    evoked.plot_image(picks=picks, axes=ax, colorbar=False, show=False,
                      clim=dict(eeg=(-vmax, vmax)), mask=significant_points,
                      **time_unit, show_names="all")
    evoked.nave = None  # to suppress printing trial count for other images
    if not ax.is_last_row():  # remove xticklabels for all but bottom axis
        ax.set(xlabel='', xticklabels=[])
    ax.set(ylabel='', title=selection_name)

fig.colorbar(ax.images[-1], ax=axes, fraction=.1, aspect=20,
             pad=.05, shrink=2 / 3, label="uV", orientation="vertical")

plt.show()
