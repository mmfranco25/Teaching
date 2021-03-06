import numpy as np
import re
import matplotlib.pyplot as mp
from astropy.stats import LombScargle
from scipy import stats
import peakutils
from astropy.stats import sigma_clip
from IPython import display

# reads in light curve data from a file
def read_lcv(lcv_file):

    dtype = np.dtype([('filter', 'S2'), ('mjd', float), ('mag', float),
        ('err', float)])
    data = np.loadtxt(lcv_file, dtype=dtype)

    filters = np.unique(data['filter'])

    return filters, data

# phases a light curve with a given period - produces plot and text file if prompted
def phase_lcv(lcv_data, lcv_name, period, T0=0, plot=1, save=0, \
        error_threshold=0.05, save_dir=''):

    phase_all = np.mod((lcv_data['mjd']-T0)/period, 1)
    select_err = lcv_data['err'] < error_threshold

    phase = phase_all[select_err]
    mag = lcv_data['mag'][select_err]
    mjd = lcv_data['mjd'][select_err]
    err = lcv_data['err'][select_err]
    band = lcv_data['filter'][select_err]

    if save == 1:
        phased_file = save_dir+lcv_name+'.ph'

        data_save = np.array(zip(lcv_data['filter'], lcv_data['mjd'], phase_all, lcv_data['mag'], lcv_data['err']), dtype=ph_dtype)
        np.savetxt(phased_file, data_save, fmt='%2s %10.4f %8.6f %6.3f %5.3f')

    if plot == 1:
        figtosave = mp.figure(figsize=(8,10))
        ax = figtosave.add_subplot(111)

        master_filters = np.array(['U', 'B', 'V', 'R', 'I', 'J', 'H', 'K',
            'I1', 'I2'], dtype='S2')
        master_markers = np.array(['P', 'v', 'D', '>', 'x', 'p', 'd', '^', 'o', 's'])
        master_offset = np.array([1.0, 0.5, 0.0, -0.25, -0.5, -0.7, -0.9, -1.1, -1.0, -1.5 ])
        master_colors = np.array(['xkcd:violet', 'xkcd:periwinkle', 'xkcd:sapphire',
            'xkcd:sky blue', 'xkcd:emerald', 'xkcd:avocado', 'xkcd:goldenrod',
            'xkcd:orange', 'xkcd:pink', 'xkcd:scarlet'])
        for filt in master_filters:
            offset = master_offset[master_filters == filt]
            marker = master_markers[master_filters == filt][0]
            color = master_colors[master_filters == filt][0]
            f_select = band == filt
            x = phase[f_select]
            y = mag[f_select]
            e = err[f_select]
            ax.errorbar(x, y+offset, yerr=e, fmt=marker, color=color, zorder=1, label=filt)
        max_mag = np.nanmean(lcv_data['mag'][lcv_data['filter'] == 'V'])+3
        min_mag = np.nanmean(lcv_data['mag'][lcv_data['filter'] == 'V'])-5
        ax.set_ylim((max_mag, min_mag))
        ax.set_xlim((-0.2, 1.2))
        ax.set_xlabel('Phase')
        ax.set_ylabel('Mag + offset')
        #add lcv name and period to plot
        ax.text(1.0, min_mag+0.25, lcv_name)
        ax.text(1.0, min_mag+0.5, 'P = '+str(period))
        #handles, labels = ax.get_legend_handles_labels()
        #ax.legend(handles, labels, loc=1)
        plot_file = save_dir+lcv_name+'-ph.pdf' #re.sub('\.ph', '-fit.pdf', phased_lcv_file)
        mp.savefig(plot_file)

# Refines the period estimated by Lomb-Scargle by minimizing the dispersion in the
# phased light curve in one or two bands.
def refine_period(first_band, best_period, second_band=None,
    error_threshold=0.05, search_window=0.0002, plot=0):

    x = np.array(first_band['mjd'][first_band['err'] < error_threshold], dtype=float)
    y = np.array(first_band['mag'][first_band['err'] < error_threshold], dtype=float)
    er = np.array(first_band['err'][first_band['err'] < error_threshold], dtype=float)
    if second_band is not None:
        x2 = np.array(second_band['mjd'][second_band['err'] < error_threshold], dtype=float)
        y2 = np.array(second_band['mag'][second_band['err'] < error_threshold], dtype=float)
        er2 = np.array(second_band['err'][second_band['err'] < error_threshold], dtype=float)

    # Calculate required precision
    delta_time = np.max(x) - np.min(x)
    approx_p = np.round(best_period, 1)
    n_cycles = np.floor(delta_time/approx_p)
    max_precision = n_cycles * approx_p / (n_cycles - 0.01) - approx_p
    order = np.ceil(np.abs(np.log10(max_precision)))
    precision = 10**order
    best_period = np.round(best_period, decimals=int(order))

    grid_num = search_window*precision

    if grid_num > 100000:
        grid_num = 100000
    min_period = best_period - search_window/2
    max_period = best_period + search_window/2
    periods = np.linspace(min_period, max_period, num=grid_num+1)
    avg_std = np.zeros(len(periods))
    for ind2, trial_period in enumerate(periods):
        phase = np.mod(x/trial_period, 1)
        stds, edges, bin_num = stats.binned_statistic(phase, y, statistic=np.std, bins=100)
        counts, edges, bin_num = stats.binned_statistic(phase, y, statistic='count', bins=100)
        if second_band is not None:
            phase2 = np.mod(x2/trial_period, 1)
            stds2, edges2, bin_num2 = stats.binned_statistic(phase2, y2, statistic=np.std, bins=100)
            counts2, edges2, bin_num2 = stats.binned_statistic(phase2, y2, statistic='count', bins=100)
            avg_std[ind2] = np.mean(stds2[counts2 > 3]) + np.mean(stds[counts > 3])
        else:
            avg_std[ind2] = np.mean(stds[counts > 3])
    order = np.argsort(avg_std)
    new_period = periods[order[0]]
    best_std = avg_std[order[0]]

    if plot == 1:
        mp.plot(periods, avg_std, 'ro')
        mp.axvline(new_period)
        mp.show()

    return new_period


# Use to do one round of LombScargle and identify possible periods for RRL star
def period_search(data, min_period = 0.2, max_period=1.0,
                    error_threshold=0.05, verbose=0, plot=1):

    x1 = np.array(data['mjd'][data['err'] < error_threshold], dtype=float)
    y1 = np.array(data['mag'][data['err'] < error_threshold], dtype=float)
    er1 = np.array(data['err'][data['err'] < error_threshold], dtype=float)

    freq_max = 1./(min_period)
    freq_min = 1./(max_period)
    frequency, power = LombScargle(x1, y1, er1).autopower(minimum_frequency=freq_min,
                        maximum_frequency=freq_max )

    # Calculate noise level
    median_power = np.median(power)

    # Find peaks
    indices = peakutils.indexes(power, thres=0.5, min_dist=5000 )
    candidate_periods = 1/frequency[indices]
    best_frequency = frequency[np.argmax(power)]
    best_period = 1/best_frequency

    alias_freq = np.array([best_frequency+1, best_frequency-1, best_frequency+2, best_frequency-2])
    alias_power = np.repeat(np.max(power), 4)



    # Calculate SNR of peaks
    snr = power[indices]/median_power
    snr_best = power[np.argmax(power)]/median_power
    if verbose == 1:
        print candidate_periods
        print snr
    t_fit = np.linspace(0,1)
    y_fit = LombScargle(x1, y1, er1).model(t_fit, best_frequency)

    phase_data = np.mod(x1*best_frequency, 1)

    if plot == 1:
        fig = mp.figure(figsize=(12, 6))
        ax1 = mp.subplot2grid((1,2), (0,0))
        ax2 = mp.subplot2grid((1,2), (0,1))
        ax1.plot(1/frequency, power)
        ax1.plot(1/best_frequency, np.max(power), 'rx')
        #ax1.plot(1/frequency[indices], power[indices], 'rx')
        #ax1.plot(1/alias_freq, alias_power, 'kx')
        ax1.set_xlim(min_period, max_period)
        ax1.set_xlabel('Period (days)')
        ax1.set_ylabel('Power')

        ax2.plot(phase_data, y1, 'o')
        ax2.set_ylim(np.max(y1)+0.05, np.min(y1)-0.05)
        ax2.set_xlabel('Phase')
        ax2.set_ylabel('mag')
        mp.show()
        mp.close()

    return best_period, snr_best

# Derives a smoothed light curve using the GLOESS method. This version also
# calculates the appropriate T0, and saves both the phased data and a
# the smoothed light curve into text files
def gloess_auto(lcv_data, period, lcv_name, clean=1, save_dir='', master_plot=1):

    master_filters = np.array(['U', 'B', 'V', 'R', 'I', 'J', 'H', 'K', 'I1', 'I2'], dtype='S2')
    # set to 1 if you want to save a single figure for each star with all data
    if master_plot == 1:
        figtosave = mp.figure(figsize=(8,10))
        ax = figtosave.add_subplot(111)
        master_markers = np.array(['P', 'v', 'D', '>', 'x', 'p', 'd', '^', 'o', 's'])
        master_offset = np.array([1.0, 0.5, 0.0, -0.25, -0.5, -0.7, -0.9, -1.1, -1.0, -1.5 ])
        master_colors = np.array(['xkcd:violet', 'xkcd:periwinkle', 'xkcd:sapphire',
            'xkcd:sky blue', 'xkcd:emerald', 'xkcd:avocado', 'xkcd:goldenrod',
            'xkcd:orange', 'xkcd:pink', 'xkcd:scarlet'])

    initial_phase = np.mod(lcv_data['mjd']/period, 1)

    # Of the available filters, the "best" filter is the one with the most epochs
    filters, counts = np.unique(lcv_data['filter'], return_counts=True)
    num_filters = len(filters)
    best_filter = filters[counts.argmax()]

    #print 'Using {} to determine epoch of min'.format(best_filter)

    dtype = np.dtype([('avg', float), ('avg_e', float), ('amp', float), ('chisq', float), ('sigma', float)])
    lcv_params = np.zeros(len(master_filters), dtype=dtype)

    band_all = []
    x_all = []
    y_all = []
    T0 = 0
    for iii, filt in enumerate(master_filters):

        available = np.in1d(filt, filters)
        if available == False: continue

        current_filter = lcv_data['filter'] == filt
        phase = initial_phase[current_filter]
        mag = lcv_data['mag'][current_filter]
        err = lcv_data['err'][current_filter]
        mjd = lcv_data['mjd'][current_filter]

        # Check for nan values and remove them
        mjd = mjd[~np.isnan(mag)]
        phase = phase[~np.isnan(mag)]
        err = err[~np.isnan(mag)]
        mag = mag[~np.isnan(mag)]

        if clean == 1:
            # remove data with large error bars
            filtered_err = sigma_clip(err, sigma=3, iters=2)
            mag = mag[~filtered_err.mask]
            phase = phase[~filtered_err.mask]
            err = err[~filtered_err.mask]
            mjd = mjd[~filtered_err.mask]

        # skip this band if we don't have enough observations or phase coverage
        n_obs = len(mag)
        if (filt == 'I1') or (filt == 'I2'): n_obs = 99
        delta_phase = np.max(phase) - np.min(phase)
        if (n_obs < 30) or (delta_phase < 0.7):
            continue

        hist, bins = np.histogram(phase, bins='auto')
        sigma = 1./len(bins)

        phase_copy = np.concatenate((phase-2, phase-1, phase, phase+1, phase+2))
        mag_copy = np.tile(mag, 5)
        err_copy = np.tile(err, 5)

        x = np.arange(0, 1, 0.001)

        n_data = len(mag_copy)
        n_fit = len(x)

        smoothed_mag = np.zeros(n_fit)
        weight = np.zeros(n_data)

        # interpolate
        for ind, step in enumerate(x):

            dist = phase_copy - step
            closest_phase = np.min(np.abs(dist))
            if closest_phase > sigma: sigma = closest_phase*5
            weight = err_copy * np.exp(dist**2/sigma**2)
            fit = np.polyfit(phase_copy, mag_copy, 2, w=1/weight)
            smoothed_mag[ind] = fit[2] + fit[1]*step + fit[0]*step**2

        smoothed_mag_copy = np.tile(smoothed_mag, 5)
        x_copy = np.concatenate((x-2, x-1, x, x+1, x+2))

        # Derive light curve parameters
        flux = 99*np.power(10,-smoothed_mag/2.5)
        average_flux = np.mean(flux)
        average_mag = -2.5*np.log10(average_flux/99)

        amplitude = np.max(smoothed_mag) - np.min(smoothed_mag)
        residual = np.zeros(len(phase))
        for ii, ph in enumerate(phase):
            dist = np.abs(x - ph)
            yy = smoothed_mag[dist == np.min(dist)]
            residual[ii] = mag[ii] - yy[0]
        chisq = np.sum(residual**2/err**2)

        # determine epoch of minimum using band with most data
        if filt == best_filter:
            ph_max = x[smoothed_mag.argmin()]
            ph_min = x[smoothed_mag.argmax()]
            T0 = mjd[np.abs(phase - ph_min).argmin()]

        err_fit = amplitude/np.sqrt(12*len(err))
        average_mag_err = np.sqrt(np.sum(err**2)/len(err)**2 + err_fit**2)


        lcv_params['avg'][iii] = average_mag
        lcv_params['avg_e'][iii] = average_mag_err
        lcv_params['amp'][iii] = amplitude
        lcv_params['chisq'][iii] = chisq
        lcv_params['sigma'][iii] = sigma

        band = np.repeat(filt, len(x))
        band_all = np.append(band_all, band)
        x_all = np.append(x_all, x)
        y_all = np.append(y_all, smoothed_mag)

    # rephase with T0
    x_new = x_all - ph_min
    x_new[x_new < 0] += 1.0
    phase_final = np.mod((lcv_data['mjd'] - T0)/period, 1)

    # sort gloess fit again
    for iii, filt in enumerate(master_filters):
        # check to see if gloess was performed for this filter
        #available = np.in1d(filt, filters)
        # if availabe == False: continue
        if lcv_params['avg'][iii] == 0: continue

        current_filter = band_all == filt
        xx = np.copy(x_new[current_filter])
        yy = np.copy(y_all[current_filter])
        order = np.argsort(xx)
        x_new[current_filter] = xx[order]
        y_all[current_filter] = yy[order]

        if master_plot == 1:
            xcopy = np.concatenate((x_new[current_filter]-1, x_new[current_filter], x_new[current_filter]+1))
            ycopy = np.tile(y_all[current_filter], 3)
            ph = phase_final[lcv_data['filter'] == filt]
            mag = lcv_data['mag'][lcv_data['filter'] == filt]
            err = lcv_data['err'][lcv_data['filter'] == filt]
            if clean == 1:
                # remove data with large error bars
                filtered_err = sigma_clip(err, sigma=3, iters=2)
                mag = mag[~filtered_err.mask]
                ph = ph[~filtered_err.mask]
                err = err[~filtered_err.mask]
            offset = master_offset[master_filters == filt]
            marker = master_markers[master_filters == filt][0]
            color = master_colors[master_filters == filt][0]
            ax.errorbar(ph, mag+offset, yerr=err, fmt=marker, color=color, zorder=1, label=filt)
            ax.plot(xcopy, ycopy+offset, 'k-')

    fit_dtype = np.dtype([('filter', 'a2'), ('ph', float), ('mag', float)])
    ph_dtype = np.dtype([('filter', 'a2'), ('mjd', float), ('phase', float), ('mag', float), ('err', float)])
    fit_file = open(save_dir+lcv_name+'.fit', 'w')
    ph_file = open(save_dir+lcv_name+'.ph', 'w')

    data_save = np.array(zip(band_all, x_new, y_all), dtype=fit_dtype)
    np.savetxt(fit_file, data_save, fmt='%2s %6.4f %6.3f')

    data_save = np.array(zip(lcv_data['filter'], lcv_data['mjd'], phase_final, lcv_data['mag'], lcv_data['err']), dtype=ph_dtype)
    np.savetxt(ph_file, data_save, fmt='%2s %10.4f %8.6f %6.3f %5.3f')

    fit_file.close()
    ph_file.close()


    if master_plot == 1:

        max_mag = np.nanmean(lcv_data['mag'][lcv_data['filter'] == 'V'])+3
        min_mag = np.nanmean(lcv_data['mag'][lcv_data['filter'] == 'V'])-5
        ax.set_ylim((max_mag, min_mag))
        ax.set_xlim((-0.2, 2.0))
        ax.set_xlabel('Phase')
        ax.set_ylabel('Mag + offset')
        #add lcv name and period to plot
        ax.text(1.0, min_mag+0.25, lcv_name)
        ax.text(1.0, min_mag+0.5, 'P = '+str(period))
        handles, labels = ax.get_legend_handles_labels()
        # sort both labels and handles by labels
        #labels, handles = zip(*sorted(zip(labels, handles), key=lambda t: t[0]))
        ax.legend(handles, labels, loc=1)
        plot_file = save_dir+lcv_name+'-fit.pdf'
        mp.savefig(plot_file, format='pdf')


    return lcv_params, T0
