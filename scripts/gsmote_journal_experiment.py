"""
Run the experimental procedure of the
Geometric SMOTE journal paper.
"""

# Author: Georgios Douzas <gdouzas@icloud.com>
# License: MIT

# Imports
from os.path import join

from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.neighbors.classification import KNeighborsClassifier
from sklearn.ensemble import GradientBoostingClassifier
from sklearnext.tools import evaluate_binary_imbalanced_experiments, read_csv_dir, summarize_binary_datasets
from sklearnext.over_sampling import RandomOverSampler, SMOTE, GeometricSMOTE

# Paths
datasets_path = join('..', 'data', 'binary-numerical-imbalanced')
results_path = join('..', 'data', 'results', 'gsmote-journal')

# Oversamplers and classifiers
oversamplers = [
    ('NO OVERSAMPLING', None),
    ('RANDOM OVERSAMPLING', RandomOverSampler(random_state=0)),
    ('SMOTE', SMOTE(random_state=1), {'k_neighbors': [3, 5]}),
    ('G-SMOTE', GeometricSMOTE(random_state=2), {
        'selection_strategy':['combined', 'minority', 'majority'],
        'k_neighbors':[3, 5],
        'truncation_factor': [-1.0, -0.5, .0, 0.25, 0.5, 0.75, 1.0],
        'deformation_factor': [.0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0]
    })
]
classifiers = [
    ('LR', LogisticRegression()),
    ('KNN', KNeighborsClassifier(), {'n_neighbors':[3, 5]}),
    ('DT', DecisionTreeClassifier(random_state=3), {'max_depth': [3, 6]}),
    ('GBC', GradientBoostingClassifier(random_state=4), {'max_depth':[3, 6], 'n_estimators':[50, 100]})
]

# Load datasets
imbalanced_datasets = read_csv_dir(datasets_path)

# Summarize datasets
imbalanced_datasets_summary = summarize_binary_datasets(imbalanced_datasets)

# Run main experiment
results = evaluate_binary_imbalanced_experiments(datasets=imbalanced_datasets,
                                                 oversamplers=oversamplers,
                                                 classifiers=classifiers,
                                                 scoring=['roc_auc', 'f1', 'geometric_mean_score'],
                                                 n_splits=5,
                                                 n_runs=3,
                                                 random_state=5)

# Save various datasets 
imbalanced_datasets_summary.to_csv(join(results_path, 'imbalanced_datasets_summary.csv'), index=False)
for name, result in results.items():
    result.to_csv(join(results_path, '%s.csv' % name), index=(name == 'aggregated'))
