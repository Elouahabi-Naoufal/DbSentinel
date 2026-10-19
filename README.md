<a id="readme-top"></a>

<!-- PROJECT SHIELDS -->
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![License][license-shield]][license-url]
[![LinkedIn][linkedin-shield]][linkedin-url]

<!-- PROJECT TITLE BLOCK -->
<br />
<div align="center">
  <a href="https://github.com/Elouahabi-Naoufal/DbSentinel">
    <h3 align="center">DbSentinel</h3>
  </a>

  <p align="center">
    A PyQt5 desktop explorer for SQLite and SQLCipher databases, with BLOB previews,
    query history and theme support. Superseded by SQLiteExplorer.
    <br />
    <a href="https://github.com/Elouahabi-Naoufal/DbSentinel"><strong>Explore the source »</strong></a>
    <br />
    <br />
    <a href="https://github.com/Elouahabi-Naoufal/DbSentinel/issues">Report Bug</a>
    &middot;
    <a href="https://github.com/Elouahabi-Naoufal/DbSentinel/issues">Request Feature</a>
  </p>
</div>

<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>

<!-- ABOUT THE PROJECT -->
## About The Project

DbSentinel is a single-file PyQt5 desktop application for opening, browsing and editing SQLite
databases. It was the first iteration of this tool and is now **archived** — [SQLiteExplorer][sqliteexplorer-url]
is the maintained PyQt6 successor and the version to use for new work.

What the application does, as implemented in `sqlite_explorer.py`:

* **Table browser** — lists every table in a sidebar and loads the selected table into a sortable grid.
* **CRUD** — insert rows through a dialog, edit cells in place, delete selected rows with a confirmation
  prompt, create tables, and add columns.
* **Encrypted databases** — detects SQLCipher-encrypted files, prompts for a password, and retries on a
  wrong password. Falls back to the standard `sqlite3` module when SQLCipher is unavailable.
* **SQL query editor** — a plain text editor that runs arbitrary SQL and displays the result set or the
  error message.
* **BLOB preview** — detects common formats from the bytes and renders images, text, Markdown, audio,
  video, PDF, and office documents, with a hex dump for anything else. BLOBs can be saved to disk.
* **Themes** — system, light and dark palettes, persisted with `QSettings`.
* **Recent databases** — the last opened files are kept in the File menu.
* **Responsive layout** — the sidebar can be hidden, and the window reflows for smaller screens.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Built With

* [![Python][Python.com]][Python-url]
* [![PyQt5][PyQt5.com]][PyQt5-url]
* [![SQLite][SQLite.com]][SQLite-url]
* [![SQLCipher][SQLCipher.com]][SQLCipher-url]

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- GETTING STARTED -->
## Getting Started

### Prerequisites

* Python 3.8 or newer.
* `PyQt5` and, for encrypted databases, `pysqlcipher3`.
* On Linux, `pysqlcipher3` may need the SQLCipher development headers:

  ```sh
  # Debian/Ubuntu
  sudo apt-get install libsqlcipher-dev python3-dev

  # Fedora
  sudo dnf install sqlcipher-devel python3-devel
  ```

### Installation

1. Clone the repository

   ```sh
   git clone https://github.com/Elouahabi-Naoufal/DbSentinel.git
   cd DbSentinel
   ```

2. Install the dependencies — either through the helper script or manually

   ```sh
   python install_dependencies.py
   ```

   ```sh
   pip install PyQt5 pysqlcipher3
   ```

3. Run the application

   ```sh
   python sqlite_explorer.py
   ```

<details>
<summary>Linux AppImage</summary>

The repository ships `DbSentinel-1.0-x86_64.AppImage` and a build script. To rebuild it:

```sh
chmod +x build_appimage.sh
./build_appimage.sh
```

See [`BUILD.md`](BUILD.md) for the manual AppDir steps.

</details>

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- USAGE EXAMPLES -->
## Usage

1. Open a database with **File → Open Database…** and select a `.db`, `.sqlite` or `.sqlite3` file. If the
   file is encrypted, enter the SQLCipher password in the prompt.
2. Click a table in the sidebar. Its schema is loaded, followed by the rows.
3. Use the buttons above the grid to add a row, edit the selected row, or delete the selection. Click a
   cell to edit it in place; the update is written on commit.
4. Use **Table → Create Table…** and **Table → Add Column…** to change the schema.
5. Open the SQL editor from the menu to run a custom statement. Results, affected-row counts and errors are
   shown in the results pane.
6. Double-click a BLOB cell to preview it. The preview dialog offers a **Save** button for exporting the
   bytes to a file.

The theme can be switched between **System**, **Light** and **Dark** from the View menu. The preference and
the recent-file list are stored with `QSettings` under the application name `DbSentinel`.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- ROADMAP -->
## Roadmap

This repository is archived and receives no further development. The items below are known limitations of
the code as it stands:

- [x] Table browsing, inline editing, row insertion and deletion
- [x] Schema creation and column addition
- [x] SQLCipher-encrypted database support
- [x] BLOB previews for images, text, audio, video, PDF and office formats
- [x] Light/dark/system themes and recent-file history
- [x] Linux AppImage build
- [ ] Continue development here — use [SQLiteExplorer][sqliteexplorer-url] instead
- [ ] There is no automated test suite
- [ ] The SQL editor is a plain `QTextEdit`; it does not provide syntax highlighting

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTRIBUTING -->
## Contributing

DbSentinel is archived, so changes are not being accepted here. If you want to improve the tool, open an
issue or pull request against [SQLiteExplorer][sqliteexplorer-url].

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Top contributors:

<a href="https://github.com/Elouahabi-Naoufal/DbSentinel/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=Elouahabi-Naoufal/DbSentinel" alt="contrib.rocks image" />
</a>

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- LICENSE -->
## License

This project is not licensed — all rights reserved.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTACT -->
## Contact

Naoufal Elouahabi - [LinkedIn](https://www.linkedin.com/in/elouahabi-naoufal/) - elouahabi-naoufal1@gmail.com

Project Link: [https://github.com/Elouahabi-Naoufal/DbSentinel](https://github.com/Elouahabi-Naoufal/DbSentinel)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- ACKNOWLEDGMENTS -->
## Acknowledgments

* [SQLite](https://www.sqlite.org/) and [SQLCipher](https://www.zetetic.net/sqlcipher/)
* [PyQt5 / Riverbank Computing](https://www.riverbankcomputing.com/software/pyqt/)
* [AppImageKit](https://github.com/AppImage/AppImageKit)
* [Img Shields](https://shields.io)
* [Choose an Open Source License](https://choosealicense.com)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/Elouahabi-Naoufal/DbSentinel.svg?style=for-the-badge
[contributors-url]: https://github.com/Elouahabi-Naoufal/DbSentinel/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/Elouahabi-Naoufal/DbSentinel.svg?style=for-the-badge
[forks-url]: https://github.com/Elouahabi-Naoufal/DbSentinel/network/members
[stars-shield]: https://img.shields.io/github/stars/Elouahabi-Naoufal/DbSentinel.svg?style=for-the-badge
[stars-url]: https://github.com/Elouahabi-Naoufal/DbSentinel/stargazers
[issues-shield]: https://img.shields.io/github/issues/Elouahabi-Naoufal/DbSentinel.svg?style=for-the-badge
[issues-url]: https://github.com/Elouahabi-Naoufal/DbSentinel/issues
[license-shield]: https://img.shields.io/badge/license-unlicensed-lightgrey?style=for-the-badge
[license-url]: https://github.com/Elouahabi-Naoufal/DbSentinel
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=for-the-badge&logo=linkedin&colorB=555
[linkedin-url]: https://www.linkedin.com/in/elouahabi-naoufal/
[Python.com]: https://img.shields.io/badge/python-3776AB?style=for-the-badge&logo=python&logoColor=white
[Python-url]: https://www.python.org/
[PyQt5.com]: https://img.shields.io/badge/PyQt5-41CD52?style=for-the-badge&logo=qt&logoColor=white
[PyQt5-url]: https://www.riverbankcomputing.com/software/pyqt/
[SQLite.com]: https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white
[SQLite-url]: https://www.sqlite.org/
[SQLCipher.com]: https://img.shields.io/badge/SQLCipher-0F80C0?style=for-the-badge
[SQLCipher-url]: https://www.zetetic.net/sqlcipher/
[sqliteexplorer-url]: https://github.com/Elouahabi-Naoufal/SQLiteExplorer
