"""
Download, transform and simulate various datasets.
"""

# Author: Georgios Douzas <gdouzas@icloud.com>
# License: MIT

from sys import argv
from os.path import join, dirname, abspath
from os import remove, listdir
from re import sub
from collections import Counter
from itertools import product
from urllib.parse import urljoin
from string import ascii_lowercase
from zipfile import ZipFile
from io import BytesIO, StringIO
from sqlite3 import connect
from scipy.io import loadmat
import io
import requests

from tqdm import tqdm
import requests
import numpy as np
import pandas as pd
from sklearn.utils import check_X_y
from sklearn.metrics import SCORERS, make_scorer
from imblearn.metrics import geometric_mean_score
from imblearn.datasets import make_imbalance

UCI_URL = 'https://archive.ics.uci.edu/ml/machine-learning-databases/'
KEEL_URL = 'http://sci2s.ugr.es/keel/keel-dataset/datasets/imbalanced/'
GIC_URL = 'http://www.ehu.eus/ccwintco/uploads/'
FETCH_URLS = {
    'breast_tissue': urljoin(UCI_URL, '00192/BreastTissue.xls'),
    'ecoli': urljoin(UCI_URL, 'ecoli/ecoli.data'),
    'eucalyptus': 'https://www.openml.org/data/get_csv/3625/dataset_194_eucalyptus.arff',
    'glass': urljoin(UCI_URL, 'glass/glass.data'),
    'haberman': urljoin(UCI_URL, 'haberman/haberman.data'),
    'heart': urljoin(UCI_URL, 'statlog/heart/heart.dat'),
    'iris': urljoin(UCI_URL, 'iris/bezdekIris.data'),
    'libras': urljoin(UCI_URL, 'libras/movement_libras.data'),
    'liver': urljoin(UCI_URL, 'liver-disorders/bupa.data'),
    'pima': 'https://gist.githubusercontent.com/ktisha/c21e73a1bd1700294ef790c56c8aec1f/raw/819b69b5736821ccee93d05b51de0510bea00294/pima-indians-diabetes.csv',
    'vehicle': urljoin(UCI_URL, 'statlog/vehicle/'),
    'wine': urljoin(UCI_URL, 'wine/wine.data'),
    'new_thyroid_1': urljoin(urljoin(KEEL_URL, 'imb_IRlowerThan9/'), 'new-thyroid1.zip'),
    'new_thyroid_2': urljoin(urljoin(KEEL_URL, 'imb_IRlowerThan9/'), 'new-thyroid2.zip'),
    'cleveland': urljoin(urljoin(KEEL_URL, 'imb_IRhigherThan9p2/'), 'cleveland-0_vs_4.zip'),
    'dermatology': urljoin(urljoin(KEEL_URL, 'imb_IRhigherThan9p3/'), 'dermatology-6.zip'),
    'led': urljoin(urljoin(KEEL_URL, 'imb_IRhigherThan9p2/'), 'led7digit-0-2-4-5-6-7-8-9_vs_1.zip'),
    'page_blocks_1_3': urljoin(urljoin(KEEL_URL, 'imb_IRhigherThan9p1/'), 'page-blocks-1-3_vs_4.zip'),
    'vowel': urljoin(urljoin(KEEL_URL, 'imb_IRhigherThan9p1/'), 'vowel0.zip'),
    'yeast_1': urljoin(urljoin(KEEL_URL, 'imb_IRlowerThan9/'), 'yeast1.zip'),
    'banknote_authentication': urljoin(UCI_URL, '00267/data_banknote_authentication.txt'),
    'arcene': urljoin(UCI_URL, 'arcene/'),
    'audit': urljoin(UCI_URL, '00475/audit_data.zip'),
    'spambase': urljoin(UCI_URL, 'spambase/spambase.data'),
    'parkinsons': urljoin(UCI_URL, 'parkinsons/parkinsons.data'),
    'ionosphere': urljoin(UCI_URL, 'ionosphere/ionosphere.data'),
    'breast_cancer': urljoin(UCI_URL, 'breast-cancer-wisconsin/wdbc.data'),
    'indian_pines': [urljoin(GIC_URL,'2/22/Indian_pines.mat'), urljoin(GIC_URL,'c/c4/Indian_pines_gt.mat')],
    'salinas': [urljoin(GIC_URL,'f/f1/Salinas.mat'), urljoin(GIC_URL,'f/fa/Salinas_gt.mat')],
    'salinas_a': [urljoin(GIC_URL,'d/df/SalinasA.mat'), urljoin(GIC_URL,'a/aa/SalinasA_gt.mat')],
    'pavia_centre': [urljoin(GIC_URL,'e/e3/Pavia.mat'), urljoin(GIC_URL,'5/53/Pavia_gt.mat')],
    'pavia_university': [urljoin(GIC_URL,'e/ee/PaviaU.mat'), urljoin(GIC_URL,'5/50/PaviaU_gt.mat')],
    'kennedy_space_center': [urljoin(GIC_URL,'2/26/KSC.mat'), urljoin(GIC_URL,'a/a6/KSC_gt.mat')],
    'botswana': [urljoin(GIC_URL,'7/72/Botswana.mat'), urljoin(GIC_URL,'5/58/Botswana_gt.mat')]
}
MULTIPLICATION_FACTORS = [2, 3]
RANDOM_STATE = 0


class Datasets:
    """Class to download and save datasets."""

    def __init__(self, names='all'):
        self.names = names

    @staticmethod
    def _modify_columns(data):
        """Rename and reorder columns of dataframe."""
        X, y = data.drop(columns='target'), data.target
        X.columns = range(len(X.columns))
        return pd.concat([X, y], axis=1)

    def download(self):
        """Download the datasets."""
        if self.names == 'all':
            func_names = [func_name for func_name in dir(self) if 'fetch_' in func_name]
        else:
            func_names = [f'fetch_{name}'.lower().replace(' ', '_') for name in self.names]
        self.datasets_ = []
        for func_name in tqdm(func_names, desc='Datasets'):
            name = func_name.replace('fetch_', '').upper().replace('_', ' ')
            fetch_data = getattr(self, func_name)
            data = self._modify_columns(fetch_data())
            self.datasets_.append((name, data))
        return self

    def save(self, path, db_name):
        """Save datasets."""
        with connect(join(path, f'{db_name}.db')) as connection:
            for name, data in self.datasets_:
                data.to_sql(name, connection, index=False, if_exists='replace')


class ImbalancedBinaryDatasets(Datasets):
    """Class to download, transform and save binary class imbalanced datasets."""

    @staticmethod
    def _calculate_ratio(multiplication_factor, y):
        """Calculate ratio based on IRs multiplication factor."""
        ratio = Counter(y).copy()
        ratio[1] = int(ratio[1] / multiplication_factor)
        return ratio

    def _make_imbalance(self, data, multiplication_factor):
        """Undersample the minority class."""
        X_columns = [col for col in data.columns if col != 'target']
        X, y = check_X_y(data.loc[:, X_columns], data.target)
        if multiplication_factor > 1.0:
            sampling_strategy = self._calculate_ratio(multiplication_factor, y)
            X, y = make_imbalance(X, y, sampling_strategy=sampling_strategy, random_state=RANDOM_STATE)
        data = pd.DataFrame(np.column_stack((X, y)))
        data.iloc[:, -1] = data.iloc[:, -1].astype(int)
        return data

    def download(self):
        """Download the datasets and append undersampled versions of them."""
        super(ImbalancedBinaryDatasets, self).download()
        undersampled_datasets = []
        for (name, data), factor in list(product(self.datasets_, MULTIPLICATION_FACTORS)):
            ratio = self._calculate_ratio(factor, data.target)
            if ratio[1] >= 15:
                data = self._make_imbalance(data, factor)
                undersampled_datasets.append((f'{name} ({factor})', data))
        self.datasets_ += undersampled_datasets
        return self

    def fetch_breast_tissue(self):
        """Download and transform the Breast Tissue Data Set.
        The minority class is identified as the `car` and `fad`
        labels and the majority class as the rest of the labels.

        http://archive.ics.uci.edu/ml/datasets/breast+tissue
        """
        data = pd.read_excel(FETCH_URLS['breast_tissue'], sheet_name='Data')
        data = data.drop(columns='Case #').rename(columns={'Class': 'target'})
        data['target'] = data['target'].isin(['car', 'fad']).astype(int)
        return data

    def fetch_ecoli(self):
        """Download and transform the Ecoli Data Set.
        The minority class is identified as the `pp` label
        and the majority class as the rest of the labels.

        https://archive.ics.uci.edu/ml/datasets/ecoli
        """
        data = pd.read_csv(FETCH_URLS['ecoli'], header=None, delim_whitespace=True)
        data = data.drop(columns=0).rename(columns={8: 'target'})
        data['target'] = data['target'].isin(['pp']).astype(int)
        return data

    def fetch_eucalyptus(self):
        """Download and transform the Eucalyptus Data Set.
        The minority class is identified as the `best` label
        and the majority class as the rest of the labels.

        https://www.openml.org/d/188
        """
        data = pd.read_csv(FETCH_URLS['eucalyptus'])
        data = data.iloc[:, -9:].rename(columns={'Utility': 'target'})
        data = data[data != '?'].dropna()
        data['target'] = data['target'].isin(['best']).astype(int)
        return data

    def fetch_glass(self):
        """Download and transform the Glass Identification Data Set.
        The minority class is identified as the `1` label
        and the majority class as the rest of the labels.

        https://archive.ics.uci.edu/ml/datasets/glass+identification
        """
        data = pd.read_csv(FETCH_URLS['glass'], header=None)
        data = data.drop(columns=0).rename(columns={10: 'target'})
        data['target'] = data['target'].isin([1]).astype(int)
        return data

    def fetch_haberman(self):
        """Download and transform the Haberman's Survival Data Set.
        The minority class is identified as the `1` label
        and the majority class as the `0` label.

        https://archive.ics.uci.edu/ml/datasets/Haberman's+Survival
        """
        data = pd.read_csv(FETCH_URLS['haberman'], header=None)
        data.rename(columns={3: 'target'}, inplace=True)
        data['target'] = data['target'].isin([2]).astype(int)
        return data

    def fetch_heart(self):
        """Download and transform the Heart Data Set.
        The minority class is identified as the `2` label
        and the majority class as the `1` label.

        http://archive.ics.uci.edu/ml/datasets/statlog+(heart)
        """
        data = pd.read_csv(FETCH_URLS['heart'], header=None, delim_whitespace=True)
        data.rename(columns={13: 'target'}, inplace=True)
        data['target'] = data['target'].isin([2]).astype(int)
        return data

    def fetch_iris(self):
        """Download and transform the Iris Data Set.
        The minority class is identified as the `1` label
        and the majority class as the rest of the labels.

        https://archive.ics.uci.edu/ml/datasets/iris
        """
        data = pd.read_csv(FETCH_URLS['iris'], header=None)
        data.rename(columns={4: 'target'}, inplace=True)
        data['target'] = data['target'].isin(['Iris-setosa']).astype(int)
        return data

    def fetch_libras(self):
        """Download and transform the Libras Movement Data Set.
        The minority class is identified as the `1` label
        and the majority class as the rest of the labels.

        https://archive.ics.uci.edu/ml/datasets/Libras+Movement
        """
        data = pd.read_csv(FETCH_URLS['libras'], header=None)
        data.rename(columns={90: 'target'}, inplace=True)
        data['target'] = data['target'].isin([1]).astype(int)
        return data

    def fetch_liver(self):
        """Download and transform the Liver Disorders Data Set.
        The minority class is identified as the `1` label
        and the majority class as the '2' label.

        https://archive.ics.uci.edu/ml/datasets/liver+disorders
        """
        data = pd.read_csv(FETCH_URLS['liver'], header=None)
        data.rename(columns={6: 'target'}, inplace=True)
        data['target'] = data['target'].isin([1]).astype(int)
        return data

    def fetch_pima(self):
        """Download and transform the Pima Indians Diabetes Data Set.
        The minority class is identified as the `1` label
        and the majority class as the '0' label.

        https://www.kaggle.com/uciml/pima-indians-diabetes-database
        """
        data = pd.read_csv(FETCH_URLS['pima'], header=None, skiprows=9)
        data.rename(columns={8: 'target'}, inplace=True)
        return data

    def fetch_vehicle(self):
        """Download and transform the Vehicle Silhouettes Data Set.
        The minority class is identified as the `1` label
        and the majority class as the rest of the labels.

        https://archive.ics.uci.edu/ml/datasets/Statlog+(Vehicle+Silhouettes)
        """
        data = pd.DataFrame()
        for letter in ascii_lowercase[0:9]:
            partial_data = pd.read_csv(urljoin(FETCH_URLS['vehicle'], 'xa%s.dat'% letter), header=None, delim_whitespace=True)
            partial_data = partial_data.rename(columns={18: 'target'})
            partial_data['target'] = partial_data['target'].isin(['van']).astype(int)
            data = data.append(partial_data)
        return data

    def fetch_wine(self):
        """Download and transform the Wine Data Set.
        The minority class is identified as the `2` label
        and the majority class as the rest of the labels.

        https://archive.ics.uci.edu/ml/datasets/wine
        """
        data = pd.read_csv(FETCH_URLS['wine'], header=None)
        data.rename(columns={0: 'target'}, inplace=True)
        data['target'] = data['target'].isin([2]).astype(int)
        return data

    def fetch_new_thyroid_1(self):
        """Download and transform the Thyroid 1 Disease Data Set.
        The minority class is identified as the `positive`
        label and the majority class as the `negative` label.

        http://sci2s.ugr.es/keel/dataset.php?cod=145
        """
        zipped_data = requests.get(FETCH_URLS['new_thyroid_1']).content
        unzipped_data = ZipFile(BytesIO(zipped_data)).read('new-thyroid1.dat').decode('utf-8')
        data = pd.read_csv(StringIO(sub(r'@.+\n+', '', unzipped_data)), header=None, sep=', ', engine='python')
        data.rename(columns={5: 'target'}, inplace=True)
        data['target'] = data['target'].isin(['positive']).astype(int)
        return data

    def fetch_new_thyroid_2(self):
        """Download and transform the Thyroid 2 Disease Data Set.
        The minority class is identified as the `positive`
        label and the majority class as the `negative` label.

        http://sci2s.ugr.es/keel/dataset.php?cod=146
        """
        zipped_data = requests.get(FETCH_URLS['new_thyroid_2']).content
        unzipped_data = ZipFile(BytesIO(zipped_data)).read('newthyroid2.dat').decode('utf-8')
        data = pd.read_csv(StringIO(sub(r'@.+\n+', '', unzipped_data)), header=None, sep=', ', engine='python')
        data.rename(columns={5: 'target'}, inplace=True)
        data['target'] = data['target'].isin(['positive']).astype(int)
        return data

    def fetch_cleveland(self):
        """Download and transform the Heart Disease Cleveland Data Set.
        The minority class is identified as the `positive` label and
        the majority class as the `negative` label.

        http://sci2s.ugr.es/keel/dataset.php?cod=980
        """
        zipped_data = requests.get(FETCH_URLS['cleveland']).content
        unzipped_data = ZipFile(BytesIO(zipped_data)).read('cleveland-0_vs_4.dat').decode('utf-8')
        data = pd.read_csv(StringIO(sub(r'@.+\n+', '', unzipped_data)), header=None)
        data.rename(columns={13: 'target'}, inplace=True)
        data['target'] = data['target'].isin(['positive']).astype(int)
        return data

    def fetch_dermatology(self):
        """Download and transform the Dermatology Data Set.
        The minority class is identified as the `positive` label and
        the majority class as the `negative` label.

        http://sci2s.ugr.es/keel/dataset.php?cod=1330
        """
        zipped_data = requests.get(FETCH_URLS['dermatology']).content
        unzipped_data = ZipFile(BytesIO(zipped_data)).read('dermatology-6.dat').decode('utf-8')
        data = pd.read_csv(StringIO(sub(r'@.+\n+', '', unzipped_data)), header=None)
        data.rename(columns={34: 'target'}, inplace=True)
        data['target'] = data['target'].isin(['positive']).astype(int)
        return data

    def fetch_led(self):
        """Download and transform the LED Display Domain Data Set.
        The minority class is identified as the `positive` label and
        the majority class as the `negative` label.

        http://sci2s.ugr.es/keel/dataset.php?cod=998
        """
        zipped_data = requests.get(FETCH_URLS['led']).content
        unzipped_data = ZipFile(BytesIO(zipped_data)).read('led7digit-0-2-4-5-6-7-8-9_vs_1.dat').decode('utf-8')
        data = pd.read_csv(StringIO(sub(r'@.+\n+', '', unzipped_data)), header=None)
        data.rename(columns={7: 'target'}, inplace=True)
        data['target'] = data['target'].isin(['positive']).astype(int)
        return data

    def fetch_page_blocks_1_3(self):
        """Download and transform the Page Blocks 1-3 Data Set.
        The minority class is identified as the `positive` label and
        the majority class as the `negative` label.

        http://sci2s.ugr.es/keel/dataset.php?cod=124
        """
        zipped_data = requests.get(FETCH_URLS['page_blocks_1_3']).content
        unzipped_data = ZipFile(BytesIO(zipped_data)).read('page-blocks-1-3_vs_4.dat').decode('utf-8')
        data = pd.read_csv(StringIO(sub(r'@.+\n+', '', unzipped_data)), header=None)
        data.rename(columns={10: 'target'}, inplace=True)
        data['target'] = data['target'].isin(['positive']).astype(int)
        return data

    def fetch_vowel(self):
        """Download and transform the Vowel Recognition Data Set.
        The minority class is identified as the `positive` label and
        the majority class as the `negative` label.

        http://sci2s.ugr.es/keel/dataset.php?cod=127
        """
        zipped_data = requests.get(FETCH_URLS['vowel']).content
        unzipped_data = ZipFile(BytesIO(zipped_data)).read('vowel0.dat').decode('utf-8')
        data = pd.read_csv(StringIO(sub(r'@.+\n+', '', unzipped_data)), header=None)
        data.rename(columns={13: 'target'}, inplace=True)
        data['target'] = data['target'].isin([' positive']).astype(int)
        return data

    def fetch_yeast_1(self):
        """Download and transform the Yeast 1 Data Set.
        The minority class is identified as the `positive` label and
        the majority class as the `negative` label.

        http://sci2s.ugr.es/keel/dataset.php?cod=153
        """
        zipped_data = requests.get(FETCH_URLS['yeast_1']).content
        unzipped_data = ZipFile(BytesIO(zipped_data)).read('yeast1.dat').decode('utf-8')
        data = pd.read_csv(StringIO(sub(r'@.+\n+', '', unzipped_data)), header=None)
        data.rename(columns={8: 'target'}, inplace=True)
        data['target'] = data['target'].isin([' positive']).astype(int)
        return data


class BinaryDatasets(Datasets):
    """Class to download, transform and save binary class datasets."""

    def fetch_banknote_authentication(self):
        """Download and transform the Banknote Authentication Data Set.

        https://archive.ics.uci.edu/ml/datasets/banknote+authentication
        """
        data = pd.read_csv(FETCH_URLS['banknote_authentication'], header=None)
        data.rename(columns={4: 'target'}, inplace=True)
        return data

    def fetch_arcene(self):
        """Download and transform the Arcene Data Set.

        https://archive.ics.uci.edu/ml/datasets/Arcene
        """
        url = FETCH_URLS['arcene']
        data, labels = [], []
        for data_type in ('train', 'valid'):
            data.append(pd.read_csv(urljoin(url, f'ARCENE/arcene_{data_type}.data'), header=None, sep=' ').drop(columns=list(range(1998, 10001))))
            labels.append(pd.read_csv(urljoin(url, ('ARCENE/' if data_type == 'train' else '') + f'arcene_{data_type}.labels'), header=None).rename(columns={0:'target'}))
        data = pd.concat(data, ignore_index=True)
        labels = pd.concat(labels, ignore_index=True)
        data = pd.concat([data, labels], axis=1)
        data['target'] = data['target'].isin([1]).astype(int)
        return data

    def fetch_audit(self):
        """Download and transform the Audit Data Set.

        https://archive.ics.uci.edu/ml/datasets/Audit+Data
        """
        zipped_data = requests.get(FETCH_URLS['audit']).content
        unzipped_data = ZipFile(BytesIO(zipped_data)).read('audit_data/audit_risk.csv').decode('utf-8')
        data = pd.read_csv(StringIO(sub(r'@.+\n+', '', unzipped_data)), engine='python')
        data = data.drop(columns=['LOCATION_ID']).rename(columns={'Risk': 'target'}).dropna()
        return data

    def fetch_spambase(self):
        """Download and transform the Spambase Data Set.

        https://archive.ics.uci.edu/ml/datasets/Spambase
        """
        data = pd.read_csv(FETCH_URLS['spambase'], header=None)
        data.rename(columns={57: 'target'}, inplace=True)
        return data


    def fetch_parkinsons(self):
        """Download and transform the Parkinsons Data Set.

        https://archive.ics.uci.edu/ml/datasets/parkinsons
        """
        data = pd.read_csv(FETCH_URLS['parkinsons'])
        data = pd.concat([data.drop(columns=['name', 'status']), data[['status']].rename(columns={'status': 'target'})], axis=1)
        data['target'] = data['target'].isin([0]).astype(int)
        return data


    def fetch_ionosphere(self):
        """Download and transform the Ionosphere Data Set.

        https://archive.ics.uci.edu/ml/datasets/ionosphere
        """
        data = pd.read_csv(FETCH_URLS['ionosphere'], header=None)
        data = data.drop(columns=[0, 1]).rename(columns={34: 'target'})
        data['target'] = data['target'].isin(['b']).astype(int)
        return data


    def fetch_breast_cancer(self):
        """Download and transform the Breast Cancer Wisconsin Data Set.

        https://archive.ics.uci.edu/ml/datasets/Breast+Cancer+Wisconsin+(Diagnostic)
        """
        data = pd.read_csv(FETCH_URLS['breast_cancer'], header=None)
        data = pd.concat([data.drop(columns=[0, 1]), data[[1]].rename(columns={1: 'target'})], axis=1)
        data['target'] = data['target'].isin(['M']).astype(int)
        return data


class RemoteSensingDatasets(Datasets):
    """Class to download, transform and save remote sensing datasets."""

    def _load_gic_dataset(self, dataset_name):
        for url in FETCH_URLS[dataset_name]:
            r = requests.get(url, stream=True)
            content = loadmat(io.BytesIO(r.content))
            arr = np.array(list(content.values())[-1])
            arr = np.expand_dims(arr, -1) if arr.ndim==2 else arr
            yield arr

    def fetch_indian_pines(self):
        """Download and transform the Indian Pines Data Set.

        http://www.ehu.eus/ccwintco/index.php/Hyperspectral_Remote_Sensing_Scenes#Indian_Pines
        """
        return img_array_to_pandas(*self._load_gic_dataset('indian_pines'))

    def fetch_salinas(self):
        """Download and transform the Salinas Data Set.

        http://www.ehu.eus/ccwintco/index.php/Hyperspectral_Remote_Sensing_Scenes#Salinas_scene
        """
        return img_array_to_pandas(*self._load_gic_dataset('salinas'))

    def fetch_salinas_a(self):
        """Download and transform the Salinas-A Data Set.

        http://www.ehu.eus/ccwintco/index.php/Hyperspectral_Remote_Sensing_Scenes#Salinas-A_scene
        """
        return img_array_to_pandas(*self._load_gic_dataset('salinas_a'))

    def fetch_pavia_centre(self):
        """Download and transform the Pavia Centre Data Set.

        http://www.ehu.eus/ccwintco/index.php/Hyperspectral_Remote_Sensing_Scenes#Pavia_Centre_scene
        """
        return img_array_to_pandas(*self._load_gic_dataset('pavia_centre'))

    def fetch_pavia_university(self):
        """Download and transform the Pavia University Data Set.

        http://www.ehu.eus/ccwintco/index.php/Hyperspectral_Remote_Sensing_Scenes#Pavia_University_scene
        """
        return img_array_to_pandas(*self._load_gic_dataset('pavia_university'))

    def fetch_kennedy_space_center(self):
        """Download and transform the Kennedy Space Center Data Set.

        http://www.ehu.eus/ccwintco/index.php/Hyperspectral_Remote_Sensing_Scenes#Kennedy_Space_Center_.28KSC.29
        """
        return img_array_to_pandas(*self._load_gic_dataset('kennedy_space_center'))

    def fetch_botswana(self):
        """Download and transform the Botswana Data Set.

        http://www.ehu.eus/ccwintco/index.php/Hyperspectral_Remote_Sensing_Scenes#Botswana
        """
        return img_array_to_pandas(*self._load_gic_dataset('botswana'))


def img_array_to_pandas(X, y):
    """Converts an image numpy array (with ground truth) to a pandas dataframe"""
    shp  = X.shape
    columns = [i for i in range(shp[-1])]+['target']
    dat = np.concatenate([
        np.moveaxis(X, -1, 0), np.moveaxis(y, -1, 0)
    ], axis=0).reshape((len(columns), shp[0]*shp[1]))
    return pd.DataFrame(data=dat.T, columns=columns)


def load_datasets(data_path, data_type='db'):
    """Load datasets from sqlite database or csv files."""
    datasets = []
    if data_type == 'db':
        with connect(data_path) as connection:
            datasets_names = [name[0] for name in connection.execute("SELECT name FROM sqlite_master WHERE type='table';")]
            for dataset_name in datasets_names:
                ds = pd.read_sql(f'select * from "{dataset_name}"', connection)
                X, y = ds.iloc[:, :-1], ds.iloc[:, -1]
                datasets.append((dataset_name, (X, y)))
    elif data_type == 'csv':
        datasets_names = [name for name in listdir(data_path) if name.endswith('.csv')]
        for dataset_name in datasets_names:
            ds = pd.read_csv(join(data_path, dataset_name))
            name = dataset_name.replace('.csv', '').replace('_', ' ').upper()
            X, y = ds.iloc[:, :-1], ds.iloc[:, -1]
            datasets.append((name, (X, y)))
    return datasets


def generate_mean_std_tbl(mean_vals, std_vals):
    """Generate table that combines mean and sem values."""
    index = mean_vals.iloc[:, :2]
    scores = mean_vals.iloc[:, 2:].applymap('{:,.2f}'.format) + r" $\pm$ "  + std_vals.iloc[:, 2:].applymap('{:,.2f}'.format)
    tbl = pd.concat([index, scores], axis=1)
    return tbl


def generate_pvalues_tbl(tbl):
    """Format p-values."""
    for name in tbl.dtypes[tbl.dtypes == float].index:
        tbl[name] = tbl[name].apply(lambda pvalue: '%.1e' % pvalue)
    return tbl


def sort_tbl(tbl, ds_order=None, ovrs_order=None, clfs_order=None, metrics_order=None):
    """Sort tables rows and columns."""
    cols = tbl.columns
    keys = ['Dataset', 'Oversampler', 'Classifier', 'Metric']
    for key, cat in zip(keys, (ds_order, ovrs_order, clfs_order, metrics_order)):
        if key in cols:
            tbl[key] = pd.Categorical(tbl[key], categories=cat)
    key_cols = [col for col in cols if col in keys]
    tbl.sort_values(key_cols, inplace=True)
    if ovrs_order is not None and set(ovrs_order).issubset(cols):
        tbl = tbl[key_cols + list(ovrs_order)]
    return tbl


def generate_paths():
    """Generate data, results and analysis paths."""
    prefix_path = join(dirname(argv[0]), '..')
    paths = [join(prefix_path, name) for name in ('data', 'results', 'analysis')]
    return  paths


def make_bold(row, maximum=True, num_decimals=2):
    """Make bold the lowest or highest value(s)."""
    row = round(row, num_decimals)
    val = row.max() if maximum else row.min()
    mask = (row == val)
    formatter = '{0:.%sf}' % num_decimals
    row = row.apply(lambda el: formatter.format(el))
    row[mask] = '\\textbf{%s}' % formatter.format(val)
    return row


def geometric_mean_score_macro(y_true, y_pred):
    """Geometric mean score with macro average."""
    return geometric_mean_score(y_true, y_pred, average='macro')

SCORERS['geometric_mean_score_macro'] = make_scorer(geometric_mean_score_macro)
