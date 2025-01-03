# CodeAssistAnalyzer

CodeAssistAnalyzer is an extension layer for the [Petastorm](https://github.com/uber/petastorm) library. This project enhances Petastorm by analyzing its features, performance, and overall codebase quality. It adds capabilities to analyze comments, code quality metrics, and visualize code evolution over time.

## **Overview**

- **Base Library**: This project builds on top of [Petastorm](https://github.com/uber/petastorm), a library developed by Uber for data pipelines.
- **Enhancements**:
  - Integrates comment analysis using [SonarQube](https://www.sonarsource.com/).
  - Generates visualizations for metrics like comment density, code quality trends, and more.
  - Provides additional scripts to analyze changes over time.

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
- **Dependencies**:
  This project includes additional Python scripts to analyze and visualize metrics, such as:
  - `py_analyze.py`: Fetches metrics from SonarQube and processes JSON files.
  - `py_plot.py`: Generates plots for comment density and other metrics.
  - `py_plot_quarterly.py`: Focuses on quarterly trends.

- **Integration with Petastorm**:
  CodeAssistAnalyzer uses Petastorm as the base library, analyzing its core files in the `petastorm/` directory.

## **Usage Instructions**
1. Clone the repository:
   ```bash
   git clone https://github.com/armanalaa/CodeAssistAnalyzer.git
   cd CodeAssistAnalyzer
