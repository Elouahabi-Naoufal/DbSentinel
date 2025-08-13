# DbSentinel - SQLite Database Explorer

A desktop application I built for exploring and managing SQLite databases. I got tired of switching between different tools just to view database contents, so I created this all-in-one solution that handles everything from regular SQLite files to encrypted databases.

## What it does

This app lets you browse SQLite databases like you would browse files in a folder. You can see all your tables in a sidebar, click on any table to view its data, and edit records directly in the interface. I've also added support for encrypted databases using SQLCipher, which was surprisingly tricky to get working properly.

The interface is clean and responsive - I spent way too much time making sure the buttons don't overlap when you resize the window. You can hide the sidebar if you need more space, and there's a built-in SQL query editor with syntax highlighting for when you need to run custom queries.

## Key features

- Browse database tables in a clean sidebar interface
- View and edit table data directly in the main window
- Full CRUD operations - create tables, add columns, insert rows, delete records
- SQLCipher support for encrypted databases (with password prompts)
- SQL query editor with syntax highlighting and result display
- BLOB data preview for images, PDFs, videos, and other file types
- Theme support - automatically follows your system theme or you can set it manually
- Recent files menu so you can quickly reopen databases you've worked with

## Getting started

First, install the dependencies:

```bash
python install_dependencies.py
```

Or install them manually:

```bash
pip install PyQt5 pysqlcipher3
```

Then run the application:

```bash
python sqlite_explorer.py
```

If you're on Linux and want encrypted database support, you might need to install some system packages first:

```bash
# Ubuntu/Debian
sudo apt-get install libsqlcipher-dev python3-dev

# CentOS/Fedora
sudo dnf install sqlcipher-devel python3-devel
```

## How I built it

I used PyQt5 for the interface because it gives you that native desktop feel. The database operations are handled through Python's sqlite3 module, with pysqlcipher3 for the encrypted database support. 

The trickiest part was getting the BLOB preview working properly. I wanted users to be able to see images and PDFs directly in the app instead of having to export them first. The video preview with playback controls was particularly fun to implement.

I also spent a lot of time on the responsive design. The app works well whether you're using it on a small laptop screen or a large monitor. The sidebar collapses when you need more space, and all the buttons stay properly sized.

## Technical details

The app is structured with clean separation between the database operations and the UI. The DatabaseManager class handles all the SQLite interactions, while the main window manages the interface. I used Qt's model-view architecture for the table display, which makes it efficient even with large datasets.

For encrypted databases, the app automatically detects if a database is encrypted and prompts for a password. It falls back gracefully to regular SQLite if SQLCipher isn't available.

The BLOB preview system can handle images, PDFs, videos, audio files, and even displays hex dumps for binary data. I'm particularly proud of how the video player turned out - it has proper seeking and playback controls.

## Why I made this

I work with SQLite databases regularly and got frustrated with the existing tools. Some are too basic, others are overly complex, and most don't handle encrypted databases well. I wanted something that just works - open a database, see your data, make changes, done.

The app has grown from a simple table viewer into a full database management tool. I keep adding features as I find myself needing them, which is probably why it ended up with video playback support.

## Contributing

If you find bugs or want to add features, feel free to open an issue or submit a pull request. The code is straightforward to understand and modify.

## License

MIT License - use it however you want.