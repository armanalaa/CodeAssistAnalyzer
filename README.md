# CodeAssistAnalyzer

CodeAssistAnalyzer is an extension layer for the [Petastorm](https://github.com/uber/petastorm) library. This project enhances Petastorm by analyzing its features, performance, and overall codebase quality. It adds capabilities to analyze comments, code quality metrics, and visualize code evolution over time.

## **Overview**

- **Base Library**: This project builds on top of [Petastorm](https://github.com/uber/petastorm), a library developed by Uber for data pipelines.
- **Contribution**:
  - Integrates comment analysis using [SonarQube](https://www.sonarsource.com/).
  - Generates visualizations for metrics like comment density, etc.
  - Provides additional scripts to analyze changes over time.
 
  - **Integration with Petastorm**:
      CodeAssistAnalyzer uses Petastorm as the base library, analyzing its core files in the `petastorm/` directory.

## **Project Layout**

```
CodeAssistAnalyzer/
├── petastorm/                 # Original Petastorm source files
├── json/                      # Generated JSON files from SonarQube
├── scripts/                   # Additional analysis scripts
│   ├── py_analyze.py
│   ├── py_plot.py
│   ├── py_plot_quarterly.py
│   ├── py_plot_monthly.py
│   └── py_plot_weekly.py
│   └── plot_daily.py
│
├── plots/                     # Visualization output
├── sonar-project.properties   # SonarQube configuration file
└── README.md                  # Project documentation
```

## **Key Features**
1. **SonarQube Integration**:
   - Analyze code quality metrics such as comment density and code smells.
   - Generates reports in JSON format for deeper insights.

2. **Data Visualizations**:
   - Visualize daily, weekly, monthly, and quarterly trends of comment density and other code metrics.
   - Author-specific metrics and trends are highlighted.

3. **Code Evolution Analysis**:
   - Tracks the evolution of code quality and comments across different commits.
   - Leverages Git history for comprehensive insights.

## **How This Project Works**
- **Dependencies**:This project includes additional Python scripts to analyze and visualize metrics, such as:
  - `py_analyze.py`: Fetches metrics from SonarQube and processes JSON files.
  - `py_plot.py`: Generates plots for comment density and other metrics.
  - `plot_daily`: Focuses on daily trends.
  - `plot_weekly`: Focuses on weekly trends.
  - `py_plot_monthly`: Focuses on monthly trends.  
  - `py_plot_quarterly.py`: Focuses on quarterly trends.
  - `commit_hashes.txt`: includes commit hash IDs
  - `sonar-project.properties`:
    - `sonar.login`: A field for providing an authentication token to connect securely to SonarQube. Replace `squ_283ee` with your actual token.

## **Usage Instructions**

1. Clone the repository:
   ```bash
   git clone https://github.com/armanalaa/CodeAssistAnalyzer.git
   cd CodeAssistAnalyzer
   ```

2. Set up dependencies:
   - Install [SonarQube](https://www.sonarsource.com/) locally or connect to a hosted instance.
   - Ensure Python dependencies are installed:

3. Run the SonarQube scanner:
   ```bash
   sonar-scanner
   ```

4. Run analysis script:
     ```bash
     python py_analyze.py
     ```

5. Run visualize scripts:
     ```bash
       python py_plot.py
       python plot_daily
       python plot_weekly
       python py_plot_monthly  
       python py_plot_quarterly.py
     ```

## **Acknowledgments**

This project builds on the original Petastorm library by Uber. For more information, visit [Petastorm](https://github.com/uber/petastorm).

## **License**

This project is licensed under the same terms as Petastorm. See [LICENSE](LICENSE) for details.

