# Brazil's Enviromental Land Tenure: Methodology and Geospatial Processing 

## About
An integrated geospatial database that organizes and qualifies the land tenure and environmental structure of Brazil, connecting territorial data to support territorial management, analysis, and governance.
** **
## Etapas Metodológicas

The environmental land tenure algorithm consists of five main steps:

* **1 - Data Ingestion:** Collection and organization of land and territorial data, including private properties, indigenous lands, and conservation units.

* **2 - Preprocessing:** Correction of geometric inconsistencies, standardization of databases, and removal of duplicates and invalid records.

* **3 - Hierarchical:**  Defining priorities among territorial layers through multi-criteria analysis, ensuring consistency in cases of overlap.

* **4 - Layer Reclassification:** Land layers are converted to raster format, organized in a continuous grid where each pixel represents the priority defined by the AHP method.

* **5- Overlap Analysis:** Conflicts between layers are resolved by maintaining the highest priority land class in each pixel. Then, the original vectors are recovered to compose the final Enviromental Land Tenure Data.

* **6- Overlap Analysis:** Environmental assets are incorporated into the land registry, allowing for compliance analyses and the generation of environmental statistics associated with the territory.

* 
** **
## Requirements

* Python version 3.9 or higher

* QGIS Desktop version 3.44 or higher

* GDAL 

* Duckdb 



## Version History

* v 1.0
    * Construction of the Brazil Enviromental Land Tenure Dataset. 
  
  
