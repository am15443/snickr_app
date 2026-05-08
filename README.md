# Snickr — CSGY 6083 Final Project

This is my final project for Principles of Database Systems (CSGY 6083). I built a web-based messaging app called Snickr that works similarly to Slack. Users can sign up, create workspaces, make channels, send messages, invite other people, and search through messages. The whole thing runs on a PostgreSQL database with a Flask frontend.

## What I built

The app has two main parts. The first part was designing the relational database schema and writing SQL queries. The second part was building the actual web interface that connects to the database.

Features include:
- User registration and login with bcrypt password hashing
- Creating and joining workspaces
- Public, private, and direct channels
- Sending and editing messages
- Inviting users to workspaces and channels
- Searching messages by keyword (only shows results from channels you have access to)
- Bookmarking channels

## How to run it

You will need Python 3 and PostgreSQL installed.

**1. Clone the repo and set up the virtual environment**
```
git clone https://github.com/am15443/snickr_app.git
cd snickr_app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**2. Set up the database**

Make sure PostgreSQL is running, then create the database and run the schema:
```
psql -U postgres -c "CREATE DATABASE snickr;"
psql -U postgres -d snickr -f schema.sql
```

To load sample test data:
```
psql -U postgres -d snickr -f test_data.sql
```

**3. Create a .env file**

Create a file called `.env` in the root folder with your PostgreSQL password:
```
DB_PASSWORD=yourpasswordhere
```

**4. Run the app**
```
python app.py
```

Then open `http://localhost:5001` in your browser.

## Tech stack

- **Database**: PostgreSQL
- **Backend**: Python / Flask
- **Database connector**: psycopg2
- **Password hashing**: bcrypt
- **Templating**: Jinja2
- **Frontend**: Plain HTML and CSS (no frameworks)

## Project structure

```
snickr_app/
├── app.py                  # All Flask routes and database logic
├── schema.sql              # Database schema (part 1 of project)
├── test_data.sql           # Sample data for testing
├── queries.sql             # SQL queries written for part 1
├── requirements.txt        # Python dependencies
├── .env                    # Local database password (not committed)
├── .gitignore
└── templates/
    ├── base.html           # Shared layout and CSS
    ├── login.html
    ├── register.html
    ├── workspaces.html
    ├── workspace.html
    ├── channel.html
    ├── new_workspace.html
    ├── new_channel.html
    ├── invite_workspace.html
    ├── invite_channel.html
    ├── search.html
    ├── profile.html
    ├── bookmarks.html
    └── edit_message.html
```

## Database design

The schema has 9 tables. The core entities are users, workspaces, channels, and messages. Junction tables handle the many-to-many relationships between users and workspaces (workspace_members), users and channels (channel_members), and users and channels for bookmarks (bookmarks). Separate invitation tables track pending and accepted invitations for both workspaces and channels. The schema is in Third Normal Form (3NF).

## Security

- Passwords are hashed with bcrypt before being stored
- All SQL queries use parameterized statements to prevent SQL injection
- Jinja2 escapes user content automatically to prevent cross-site scripting
- Every route checks the session cookie to verify the user is logged in before doing anything
- Access control is enforced in the application — users can only see messages in channels they are members of

## Notes

This app runs locally and is not deployed anywhere. The `.env` file containing the database password is not committed to GitHub. To run it you need to create your own `.env` file as described above.