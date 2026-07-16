"""
එක වතාවක් run කරන්න ඕන migration script එකක්.

මේ වෙනස (subject select නොකර, student add උනාම සියලුම subjects වලට
auto-enroll වීම) apply කරන්න කලින් Database එකේ දැනටමත් ඉන්න students ලා
සමහරු, subjects කිහිපයකට විතරක් enroll වෙලා ඉන්නවා නම් - ඒ අඩුව මේ script
එකෙන් fix කරගන්න පුලුවන්.

මොකද කරන්නේ:
    දැනට Database එකේ ඉන්න සියලුම students, දැනට ඉන්න සියලුම subjects
    වලට enroll කරනවා (already enrolled ඒවා skip කරලා, අඩුවෙන් ඉන්නවා
    විතරක් add කරනවා). කීපවතාවක් run කලත් ප්‍රශ්නයක් නෑ.

Run කරන විදිය:
    (server එකේ / local එකේ, virtualenv එක activate කරගෙන, project root එකේදී)

    python backfill_enrollments.py

    - PythonAnywhere Bash console එකේ නම්:
        workon mini_project_env
        cd ~/mini_project
        python backfill_enrollments.py

මේ script එක අලුතෙන් subject එකක් insert_timetable.py එකෙන් add කරන හැම
වතාවකම run කරන්න (existing students ලා ඒ subject එකටත් auto-enroll වෙන්න).
"""
from app import create_app
from models import sync_all_enrollments

app = create_app()

with app.app_context():
    added = sync_all_enrollments()
    print(f"{added} enrollment record(s) added (missing pairs were backfilled).")