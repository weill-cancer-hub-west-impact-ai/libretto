# Libretto: LLM Extract Interface

Libretto is an interactive interface to visualize, compare, and refine LLM-based information extraction workflows on clinical notes.

![Screenshot of the Libretto interface.](/assets/screenshot.png)

## Quick Start

The easiest way to run Libretto is using Docker Compose, which orchestrates all services automatically.

### Prerequisites

- **Docker** - Install from [docker.com](https://docs.docker.com/get-docker/)
- **Docker Compose** - Usually included with Docker Desktop

### Setup

1. **Clone and navigate to the repository**:

   ```bash
   git clone <repository-url>
   cd libretto
   ```

2. **Configure environment variables**:

   ```bash
   cp .env.example .env
   # Edit .env with the required model IDs, API keys, and database configuration
   ```

   > [!TIP]
   > If you would like to run the interface from the same host with different environment variables, you can define multiple
   > environment variable files, such as `.env.project1`, `.env.project2`, etc. Then, replace the docker
   > command below with `docker compose --env-file <your-env-file> up --build`. The variables in `.env` will
   > still be applied, making it suitable for API keys and general configuration.

3. **Set up authentication secrets if desired**:

   Set the `AUTH_ENABLED` variable in your `.env` file to `1`. Then run the following to generate a secure JWT secret key and append it to the environment file:

   ```bash
   # Generate a secure random secret key and append it to .env
   openssl rand -hex 32 | sed 's/^/JWT_SECRET=/' >> .env
   ```

   Optionally, you can also set the JWT token expiry time (default is 1440 minutes = 24 hours):

   ```bash
   echo "JWT_EXPIRY_MINUTES=1440" >> .env
   ```

4. **Start all services**:

   ```bash
   docker compose up --build
   ```

   This will:
   - Build and start the FastAPI server, which will build and serve the frontend on port 8000
   - Start Redis for task queuing
   - Start the extraction worker, which will call NoteExtract when requested from the interface

5. **Access the application**:
   - Open [http://localhost:8000](http://localhost:8000) in your browser
   - The API is available at [http://localhost:8000/api](http://localhost:8000/api)

6. **Stop services**: Ctrl+C in the terminal if needed, then:
   ```bash
   docker compose down
   ```

# User and Project Management

If the `AUTH_ENABLED` environment variable is set to `1`, then Libretto requires user authentication to access the interface. User registration is admin-only - new users must be created using the management script.

Users are attached to **projects** that are associated with source databases (specified by a [SQLAlchemy Connection String](https://docs.sqlalchemy.org/en/21/core/engines.html)) as well as optional environment variables to use for extraction (e.g., API keys) and custom queries to access note metadata and note text.

Use the included `admin.py` script to manage users and projects:

```bash
# Interactive user management
python admin.py <database_connection_string>

# Example with SQLite database
python admin.py sqlite:///./databases/example_interactions.db
```

The script provides an interactive menu to:

- List, create, update, and delete users
- List, create, update, and delete projects
- Add and remove users' access to projects

## First Time Setup

After starting the application for the first time, you'll need to create at least one user account before you can access the web interface:

```bash
# Create your first user
python admin.py sqlite:///./databases/example_interactions.db
# Create a new user, then enter username and password when prompted
```

# Projects and Source Databasess

Each Libretto **project** maps to a source database, specified by a [SQLAlchemy connection string](https://docs.sqlalchemy.org/en/21/core/engines.html). SQLAlchemy supports common databases, including SQLite, DuckDB, Postgres, BigQuery, and others. Libretto currently includes drivers for SQLite and BigQuery; you may need to install a separate driver if you are using a different database engine.

> [!WARNING]
> While DuckDB is a popular and user-friendly database engine, we do not recommend it for Libretto because it does not support multiple concurrent read/write connections from different processes, which is required for Libretto's server and worker.

By default, Libretto expects the database connection you provide to contain two tables: `patients` and `notes`. They should have the following schema:

| Table    | Column Name | Type   | Description                                                                                                                                                      |
| -------- | ----------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| patients | id          | string | must be unique                                                                                                                                                   |
|          | metadata    | string | JSON-formatted string containing arbitrary patient-level metadata such as date of birth, demographics, etc. This metadata will be passed in a header to the LLM. |
| notes    | id          | string | must be unique                                                                                                                                                   |
|          | patient_id  | string | refers to patients.id                                                                                                                                            |
|          | date        | string | timestamp of the note, typically in ISO format                                                                                                                   |
|          | metadata    | string | JSON-formatted string containing arbitrary note-level metadata, such as note type. This metadata will be passed to the LLM before each note.                     |
|          | note_text   | string | raw note text                                                                                                                                                    |

## Project Customization

Apply these customizations using the `admin.py` interactive script.

1. **Custom Queries.** If you have a different schema that you would like to use, you can define a **note metadata query** and **note text query** so that Libretto knows how to extract the necessary information in the right format:

- **Note Metadata Query**: This query loads all information except the note text, with the following columns: `patient_id`, `note_id`, `note_date`, `patient_metadata`, `note_metadata`.

  ```sql
  -- Default note metadata query
  SELECT patients.id AS patient_id, notes.id AS note_id, notes.date AS note_date, patients.metadata AS patient_metadata, notes.metadata AS note_metadata
  FROM patients LEFT JOIN notes ON patients.id = notes.patient_id
  ```

- **Note Text Query**: This query loads the note text along with relevant primary keys. It must return the following columns: `note_id`, `patient_id`, `note_text`.

  ```sql
  -- Default note text query
  SELECT id AS note_id, patient_id AS patient_id, note_text FROM notes
  ```

2. **Set Read-Only.** You can specify that the source database should not be written to. If custom queries are set (see above), then the database is read-only regardless of this setting.

3. **Custom Environment Variables.** When managing a project in the `admin.py` script, you can also define custom environment variables to activate only when running extractions for a specific project. The following environment variables may be useful (additional variables shown in `.env.example`):

- `EXTRACTION_MODEL_ID`: Specify the model name to pass to LangExtract and to use for spec generation. Typically the model names take the form `provider:model-name`, such as `versa:azure/gpt-4.1-mini-2025-04-14` or `aihub:gpt-5-1`.
- API credentials (`VERSA_API_KEY`, `GOOGLE_APPLICATION_CREDENTIALS`, etc.): Pass specific API keys to charge LLM usage to alternative accounts from the default defined in your `.env`.

# Patient Import

Once a source database is initialized and has not been set as read-only, you can import patient data into it using the Libretto interface. You can input files in the following formats:

- **CSV**: Each row should represent a note. The file should contain the following columns (names must match exactly, but order may be different):

  | Column Name      | Type   | Required | Description                                                       |
  | ---------------- | ------ | -------- | ----------------------------------------------------------------- |
  | note_id          | string | ☑️       | must be unique                                                    |
  | patient_id       | string | ☑️       | refers to patients.id                                             |
  | date             | string |          | timestamp of the note, typically in ISO format                    |
  | patient_metadata | string |          | JSON-formatted string containing arbitrary patient-level metadata |
  | note_metadata    | string |          | JSON-formatted string containing arbitrary note-level metadata    |
  | note_text        | string | ☑️       | raw note text                                                     |

- **JSON**: Provide a list of Patient objects, each of which contains a list of Note objects. For example:
  ```json
  [
    {
      "patient_id": "patient_001",
      "notes": [
        {
          "note_id": "note_001",
          "note_text": "Patient presents with...",
          "metadata": {}
        }
      ],
      "metadata": {}
    }
  ]
  ```

You can also export patients in these formats from the interface, allowing you to transfer data between installations of Libretto.

# Additional Setup Instructions

## Non-Docker Deployment

If you would like to run Libretto without using Docker (e.g. to accommodate firewall restrictions or disk space constraints), use the `deploy.sh` script. For example, `./deploy.sh start` will check your dependencies, set up a virtualenv environment, start Redis, build the backend, start the web server, and start the extraction worker. `./deploy.sh stop` stops all of the running services.

_Note:_ To run Libretto with the example database without Docker, you will need to change the database connection strings to be in your local filesystem rather than in the Docker container filesystem. Change the `INTERACTION_DB_CONNECTION` environment variable to `sqlite:///databases/example_interactions.db` (note three slashes instead of four) and run the following to update the default project's connection string (repeat for any other projects you have created):

```bash
sqlite3 databases/example_interactions.db "UPDATE projects SET source_connection = 'sqlite:///databases/example.db' WHERE id = 1;"
```

In non-Docker deployment, you can also specify an environment variable file besides the default (`.env`) using the `-e` flag, e.g. `./deploy.sh start -e .my_env_vars`.

## Running Extractions Programmatically

To run the extraction methods without using the interface, you have two options:

1. **Worker script (parallelism, persistence in database).** Use this option if you have a Libretto project already set up and just want to run extractions asynchronously. First, find the project, specification, and patient IDs you want to run on (you can get the project and spec IDs from the URL when they're open in Libretto). In a terminal, run:

```bash
python -m worker --project_id <PROJECT_ID> --spec_id <SPEC_ID> --patient_ids <PATIENT_ID_1>,<PATIENT_ID_2>,...
```

See the documentation in `worker/__main__.py` for more available command-line options (including parallelism, overwriting, etc.). The results will be saved to the Libretto database and can be viewed in the interface.

2. **Python library (full customization).** Use this option to apply Libretto specification logic to arbitrary patients. Install the Libretto package (`pip install -e .`), then use code like the following (adapt for your API and data setup):

```python
# First set up your LLM API
from lab_llm import LLMApi
import litellm
api = LLMApi(litellm.completion)

# Patients are defined by a dictionary with the following schema:
patient = {
  "id": "A",
  "metadata": {},
  "notes": [{
    "id": "A1",
    "date": "2026-09-15",
    "metadata": {},
    "note_text": "The patient is experiencing shortness of breath, wheezing, and a fever of 102."
  }]
}

from libretto.prompt_only.run import run_prompt_only
results = run_prompt_only(patient, "Extract all symptom mentions under an extraction class called 'symptom'.", api, model_id="...")

# from libretto.noteextract.run import run_noteextract
# results = run_noteextract(patient, {"prompt": "...", "schema": "...", "examples": [...]}, model_id="...")
```

## Local Development Setup

**Live Reload:** By running `docker compose up --watch`, Docker will automatically reload the appropriate containers when you change their source code.

**Local Dependencies:** While not required to run through Docker, you may want to setup a Python environment with required packages installed for better support in your IDE. To do so, set up your virtual environment of choice, then run:

```bash
# For UCSF
pip install -e ".[ucsf]"
# For Stanford/SecureLLM users
pip install -e ".[securellm]"
# Others
pip install -e .
```

For frontend development, activate a recent version of NodeJS, preferably using [nvm](https://github.com/nvm-sh/nvm). Then `cd server/frontend` and run `npm install && npm run build` to build the frontend. (`npm run autobuild` will auto-rebuild when you change the source.)
