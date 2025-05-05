# ScholarlyTrust: Research Integrity Checker

**ScholarlyTrust** is a web-based tool designed to help researchers, academics, and institutions evaluate the legitimacy of journals and research papers. The tool uses metadata and confidence scores to provide insights into the credibility of journals and papers, helping users avoid predatory publishers and unreliable sources.

---

## Features

- **Journal Validation**: Check the legitimacy of journals using their ISSN.
- **Research Paper Validation**: Evaluate research papers using their DOI or title.
- **Metadata Insights**: View detailed metadata for journals and papers, including publisher, citation counts, DOAJ status, and more.
- **Confidence Scoring**: Get a confidence score (0-100%) indicating the likelihood of legitimacy.
- **User-Friendly Interface**: Built with Streamlit for an intuitive and interactive experience.

---

## How It Works

1. **Journal Validation**:
   - Enter the ISSN of the journal.
   - The tool fetches metadata and evaluates the journal's credibility based on factors like publisher reputation, DOAJ indexing, and citation impact.

2. **Research Paper Validation**:
   - Enter the DOI or title of the paper.
   - The tool analyzes metadata such as publication year, author count, and citation data to assess the paper's legitimacy.

3. **Investigation Summary**:
   - View a detailed summary of the analysis, including confidence scores and reasoning.

---

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/ScholarlyTrust.git
   cd ScholarlyTrust
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   streamlit run src/main.py
   ```

4. Open the app in your browser at `http://localhost:8501`.

---

## Folder Structure

```
ScholarlyTrust/
├── src/                      # Source code
│   ├── main.py               # Main Streamlit app
│   ├── api_utils.py          # Utility functions for API calls
│   └── ...                   # Other source files
├── requirements.txt          # Python dependencies
└── README.md                 # Project documentation
```

---

## Technologies Used

- **Python**: Core programming language.
- **Streamlit**: Framework for building the web interface.
- **Requests**: For making API calls.
- **HTML/CSS**: For custom styling in Streamlit.

---

## Contributing

Contributions are welcome! If you'd like to contribute, please fork the repository and submit a pull request.

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Acknowledgments

- **Anthropic**: For providing AI-powered insights.
- **Developed by**: [Abhishek Bakare](https://www.linkedin.com/in/abhishekbakare/)

---

## Contact

For questions or support, please contact [Abhishek Bakare](mailto:abakre5@gmail.com).