# School Academic Management System (SAMS)

A Flask-based academic workspace for students, teachers and administrators.

## Included modules
- Role-based student, teacher and administrator accounts
- Learning-resource uploads and downloads
- Assignment publishing and student submissions
- Timetabled examinations with server-persisted attempt deadlines
- Examination auto-submission when the exam page is left or the timer expires
- Examination departure event records for academic review
- Academic results entry, percentage calculation and student result viewing
- Student study-session and resource-access monitoring
- Private messages, scheduled chat requests and academic meeting links
- Announcements and in-app notifications

## Run locally
1. Create and activate a Python virtual environment.
2. Install dependencies: `pip install -r requirements.txt`
3. Set a strong `SECRET_KEY` environment variable before deployment.
4. Run: `python app.py`
5. Open `http://127.0.0.1:5000`

A first-run administrator account is created:
- Email: `admin@school.local`
- Password: `ChangeMe123!`

Change this password and set a unique secret key before exposing the system publicly.

## Important deployment notes
- Use HTTPS and a production WSGI server; do not deploy Flask's development server.
- Configure a persistent database and regular backups.
- Configure an approved teacher-account onboarding process before real school use.
- Meeting links are provided by external video-conference services; this application schedules and shares links but does not itself host video/audio.
- Browser page-departure detection is best-effort. It is not a reliable way to prove misconduct, and administrators should review events in context.
- Use an appropriate privacy notice and school policy for student activity monitoring.
