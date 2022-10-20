#!/usr/bin/env python3

import sys
import pathlib
import os
import pandas as pd
import numpy as np
import scipy.stats
import matplotlib.pyplot as plt
from dotenv import load_dotenv

load_dotenv()

START_PATH = os.getenv('START_PATH')
END_PATH = os.getenv('END_PATH')
if len(START_PATH) > 0 and START_PATH[0] == '~':
    START_PATH = os.path.expanduser(START_PATH)
if len(END_PATH) > 0 and END_PATH[0] == '~':
    END_PATH = os.path.expanduser(END_PATH)

QUANTITATIVE = False if os.getenv('QUANTITATIVE') == 'false' else True
QUANTITATIVE_THRESHOLD = os.getenv('QUANTITATIVE_THRESHOLD')
TRIAL_NUMBER = os.getenv('TRIAL_NUMBER')
FOLD_CHANGE_THRESHOLD = os.getenv('FOLD_CHANGE_THRESHOLD')


def envExists(var):
    if var is None or var == '':
        return False


# trial numbers
trial_number = 3 if not envExists(TRIAL_NUMBER) else int(TRIAL_NUMBER)
# fold change threshold
fold_change_threshold = 0.5 if not envExists(FOLD_CHANGE_THRESHOLD) else float(
    FOLD_CHANGE_THRESHOLD)
# quantitative analysis
quantitative = True if not envExists(QUANTITATIVE) else bool(QUANTITATIVE)
quantitative_threshold = 5 if not envExists(QUANTITATIVE_THRESHOLD) else int(
    QUANTITATIVE_THRESHOLD)

# input and output folder
defaultPath = str(pathlib.Path(__file__).parent.resolve()) + os.path.sep
startPath = defaultPath if not envExists(START_PATH) else (os.path.abspath(
    str(START_PATH)) + os.path.sep)
endPath = defaultPath if not envExists(
    END_PATH) else (os.path.abspath(str(END_PATH)) + os.path.sep)


def random_float(mean, std, seed=""):
    rng = np.random.default_rng() if not seed else np.random.default_rng(seed=seed)
    return rng.uniform(low=mean-std, high=mean+std)


def analyze(data_sheet: str, d: str, n: list):
    # read excel file
    xl = pd.read_excel(startPath + data_sheet, sheet_name="edited")
    xl = np.vstack((list(xl), xl.to_numpy()))

    # set denom data
    d_col = []
    for i in range(2, len(xl[0])):
        if d == xl[0][i][: (xl[0][i].index("_") if "_" in xl[0][i] else xl[0][i].index("-"))]:
            d_col.append(i)

    if len(d_col) != trial_number:
        print("Count for", d, "is not 3, please check inputs and data sheets again")
        return
    d_col = xl[:, d_col]

    # set numers data
    n_cols = {}
    for x in n:
        n_col = []
        for i in range(2, len(xl[0])):
            if x == xl[0][i][: (xl[0][i].index("_") if "_" in xl[0][i] else xl[0][i].index("-"))]:
                n_col.append(i)
        if len(n_col) != trial_number:
            print("Count for", x,
                  "is not 3, please check inputs and data sheets again")
            return
        n_cols[x] = xl[:, n_col]

    # do analysis
    analyzed = {}
    for x in n_cols:
        n_col = n_cols[x]
        total = np.hstack(
            (xl[:, 0].reshape(-1, 1), xl[:, 1].reshape(-1, 1), d_col, n_col))

        total_delete_row = []
        for i in range(2, len(total)):
            if total[i][2:].sum() == 0 or (quantitative and (total[i][2:] > quantitative_threshold).sum() < 3):
                total_delete_row.append(i)

            #OUTLIER CHECKING??? how can we achieve this in n? or can we even??? n^2 is easy
        tf = np.delete(total, total_delete_row, axis=0)

        calc = tf[2:, 2:].flatten()[tf[2:, 2:].flatten() < (
            quantitative_threshold if quantitative else 1)]
        if (sum(calc) == 0):
            # what should I do when there are no values less than 1 but are just all 0's?
            calc, mean, std = 0, 0, 0
        else:
            calc = calc[calc > 0]
            mean = np.mean(calc)
            std = np.std(calc)

        for i in range(1, len(tf)):
            for j in range(1, len(tf[0])):
                if tf[i][j] == 0:
                    tf[i][j] = random_float(mean, std)
                    tf[i][1] += ("*" if "*" not in tf[i][1] else "")

        l2fc = ["L2FC"]
        nl10pv = ["-log10(p-value)"]
        sig = [" "]

        up = []
        down = []
        rest = []
        for i in range(1, len(tf)):
            num = tf[i][5:8]
            den = tf[i][2:5]
            l2fc.append(np.log2(np.mean(num) / np.mean(den)))
            nl10pv.append(-1 * np.log10(scipy.stats.ttest_ind(num,
                          den, equal_var=False)[1])),
            if l2fc[-1] > fold_change_threshold and nl10pv[-1] > 1.30102999566:
                sig.append("UP")
                up.append([l2fc[-1], nl10pv[-1]])
            elif l2fc[-1] < -1 * fold_change_threshold and nl10pv[-1] > 1.30102999566:
                sig.append("DOWN")
                down.append([l2fc[-1], nl10pv[-1]])
            else:
                sig.append(" ")
                rest.append([l2fc[-1], nl10pv[-1]])

        up_scatter = plt.scatter([i[0] for i in up], [i[1]
                                 for i in up], c="blue")
        down_scatter = plt.scatter([i[0] for i in down], [
                                   i[1] for i in down], c="red")
        r = plt.scatter([i[0] for i in rest], [i[1] for i in rest], c="grey")
        plt.legend((up_scatter, down_scatter),
                   ("Up Regulated", "Down Regulated"))
        plt.title(d + " vs " + x)
        plt.xlabel("Log2 Fold Change")
        plt.ylabel("-Log10 P-Value")

        if not os.path.isdir(endPath + "figures"):
            os.makedirs(endPath + "figures")
        plt.savefig(endPath +
                    "figures/" + data_sheet[:data_sheet.index(".")] + "_" + d + "_VS_" + x + ".png")

        tf = np.hstack((tf, np.array(l2fc).reshape(-1, 1),
                       np.array(nl10pv).reshape(-1, 1), np.array(sig).reshape(-1, 1)))

        analyzed[x] = pd.DataFrame(tf)

    # write to excel
    writer = pd.ExcelWriter(
        endPath + data_sheet[:data_sheet.index(".xlsx")] + "_" + n[0] + ".xlsx", engine="xlsxwriter")
    for sheet in analyzed:
        analyzed[sheet].to_excel(
            writer, sheet_name=sheet, index=False, header=False)
    writer.save()


# excel file name (type all separated with ',' - no spaces)
data_sheets = str(sys.argv[1]).split(',')
# denominator
d = str(sys.argv[2])
# numerators/tabs (type all separated with ',' - no space)
n = str(sys.argv[3]).split(',')

for data_sheet in data_sheets:
    analyze(data_sheet, d, n)
