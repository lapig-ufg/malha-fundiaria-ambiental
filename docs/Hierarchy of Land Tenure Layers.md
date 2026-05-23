# 03. Hierarchical of Land Tenure Layers

This stage is responsible for identifying areas with spatial conflict — where two or more polygons from different databases coexist — and defining which land tenure class should prevail in the environmental land tenure data.
** **

![Figure 1 - Data Ingestion Flowchart](figuras/fig5_en.png)


## AHP Method (Analytic Hierarchy Process)

The resolution of overlaps is performed using the AHP (Analytic Hierarchy Process) multicriteria method, which allows assigning relative weights to the different land tenure layers based on technical criteria.

Four main criteria were considered:

1. **Legal Security:** Degree of legal backing and formal recognition of the layer
2. **Geometric Precision:** Quality and spatial accuracy of the data
3. **Overlap:** Robusteness of the layer in the face of spatial conflicts
4. **Domain Stability:** Permanence and historical consolidation of land occupation

## Evaluation Scale (Saaty)
The weights were defined based on the Saaty scale (1 to 9), used for pairwise comparisons:

* **Weight 1 - Equal Importance:** The two activities contribute equally to the objective.
* **Weight 3 - Moderate Importance:** Experience and judgment slightly favor one activity over the other.
* **Weight 5 - Strong Importance:** Experience and judgment strongly favor one activity over the other.
* **Weight 7 - Very Strong Importance:** An activity is strongly favored and its dominance is demonstrated in practice.
* **Weight 9 - Extreme Importance:** The evidence favoring one activity over the other is of the highest possible order of affirmation.

Note: The values 2, 4, 6, and 8 are used when there is doubt in the effective definition of the weight value.
## Criteria Comparison Matrix

### Table 1: Criteria Weight Matrix
| Criteria | Legal Security | Geometric Precision | Overlap | Stability |
| :--- | :--- | :--- | --- | :--- |
| Legal Security | 1 | 3 | 5 | 7 |
| Geometric Precision | 1/3 | 1 | 3 | 5 |
| Overlap | 1/5 | 1/3 | 1 | 3 |
| Stability | 1/7 | 1/5 | 1/3 | 1 |

## Normalized Weights for each layer
From the normalization of the matrix, the final weights of each criterion were obtained:

### Table 2: Normalized Criteria Weight Matrix
| Criteria | Legal Security | Geometric Precision | Overlap | Stability | Average (Weight) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Legal Security | 0.599 | 0.662 | 0.536 | 0.438 | 0.56 |
| Geometric Precision | 0.198 | 0.221 | 0.322 | 0.313 | 0.26 |
| Overlap | 0.120 | 0.073 | 0.107 | 0.188 | 0.12 |
| Stability | 0.084 | 0.044 | 0.035 | 0.063 | 0.06 |

** **
