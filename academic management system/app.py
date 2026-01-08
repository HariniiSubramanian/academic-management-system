from flask import Flask, render_template, request, redirect, url_for, flash,session
import mysql.connector


app = Flask(__name__)
app.secret_key = 'your_secret_key_change_this'

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="tt_management"
)

cursor = db.cursor()


@app.route('/',methods=['GET','POST'])
def index():
    return render_template('welcome.html')


@app.route('/signup',methods=['GET','POST'])
def signup():

    if request.method=='POST':
        name=request.form['name']
        number=request.form['number']
        email=request.form['email']
        role=request.form['role']
        password=request.form['password']
        confirm_password=request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match')
            return redirect(url_for('signup'))

        sql = """
               INSERT INTO signup (name,number, email, role, password,confirm_password)
               VALUES (%s, %s, %s, %s, %s, %s)
               """
        values = (name, number, email, role, password, confirm_password)

        cursor.execute(sql, values)
        db.commit()
        # if db.is_connected():

            # flash('Signup successful')
        return redirect(url_for('index'))

    return render_template('signup.html')

@app.route('/login',methods=['GET','POST'])
def login():

    if request.method=='POST':
        name=request.form.get('name')
        password=request.form.get('password')

        sql=""" SELECT name,role FROM signup WHERE name = %s AND password = %s """
        values=(name,password)
        cursor.execute(sql, values)
        person = cursor.fetchone()

        if person:

            session['name'] = person[0]  # 🔥 store name
            session['role'] = person[1]



            if person[1] =='student':
                return redirect(url_for('student_view'))
            elif person[1] =='staff':
                return redirect(url_for('staff_view'))
            else:
                flash('invalid field')
                return redirect(url_for('login'))

    return render_template('login.html')

# @app.route('/student')
# def student_view():
#     if 'name' not in session:
#         return redirect(url_for('login'))

#     return render_template(
#         'studview.html', name=session['name'])




@app.route('/student')
def student_view():
    if 'name' not in session:
        return redirect(url_for('login'))

    # get student info
    cursor.execute(
        "SELECT id FROM students WHERE student_name=%s",
        (session['name'],)
    )
    student = cursor.fetchone()
    student_id = student[0]

    # assigned tests (LEFT PANEL)
    cursor.execute("""
        SELECT t.id, t.title, t.questions, t.end_datetime, st.status
        FROM tests t
        JOIN student_tests st ON t.id = st.test_id
        WHERE st.student_id = %s
        ORDER BY t.end_datetime DESC
    """, (student_id,))
    tests = cursor.fetchall()

    # 🔥 WEEKLY PERFORMANCE (RIGHT TABLE)
    cursor.execute("""
        SELECT
            t.title,
            st.submitted_at,
            st.marks,
            st.status,
            st.staff_review
        FROM student_tests st
        JOIN tests t ON st.test_id = t.id
        WHERE st.student_id = %s
        ORDER BY st.submitted_at DESC
    """, (student_id,))
    performance = cursor.fetchall()

    return render_template(
        'studview.html',
        name=session['name'],
        tests=tests,
        performance=performance
    )


   

@app.route('/view_test/<int:st_id>')
def view_test(st_id):
    if 'name' not in session:
        return redirect(url_for('login'))

    cursor.execute("""
        SELECT 
            t.title,
            t.questions,
            t.end_datetime,
            st.id
        FROM student_tests st
        JOIN tests t ON st.test_id = t.id
        WHERE st.id=%s
    """, (st_id,))

    test = cursor.fetchone()
    return render_template('view_test.html', test=test)


@app.route('/submit_test/<int:test_id>', methods=['POST'])
def submit_test(test_id):

    file = request.files['answer_file']
    filename = file.filename
    file.save(f"static/uploads/{filename}")

    cursor.execute("""
        UPDATE student_tests
        SET file_path=%s, status='Submitted', submitted_at=NOW()
        WHERE test_id=%s
    """, (filename, test_id))

    db.commit()
    return redirect(url_for('student_view'))



# staff ui backend functions....

@app.route('/staff')
def staff_view():

    if 'name' not in session:
        return redirect(url_for('login'))

    batch = request.args.get('batch', 'Batch 1')

    # students list (attendance)
    cursor.execute(
        "SELECT * FROM students WHERE batch=%s",
        (batch,)
    )
    students = cursor.fetchall()

    # 🔥 REVIEW DATA (student uploaded files)
    cursor.execute("""
        SELECT 
            s.student_name,
            s.student_id,
            s.batch,
            t.title,
            st.file_path,
            st.submitted_at,
            st.status,
            st.id
        FROM student_tests st
        JOIN students s ON st.student_id = s.id
        JOIN tests t ON st.test_id = t.id
        WHERE s.batch = %s
          AND st.file_path IS NOT NULL
    """, (batch,))

    reviews = cursor.fetchall()

    return render_template(
        'staffview.html',
        name=session['name'],
        students=students,
        reviews=reviews,
        selected_batch=batch
    )




@app.route('/add_student', methods=['POST'])
def add_student():
    name = request.form['student_name']
    sid = request.form['student_id']
    course = request.form['course']
    batch = request.form['batch']

    cursor.execute(
        "INSERT INTO students (student_name, student_id, course, batch) VALUES (%s,%s,%s,%s)",
        (name, sid, course, batch)
    )
    db.commit()

    return redirect(url_for('staff_view', batch=batch))


@app.route('/mark_attendance/<int:stud_id>/<status>')
def mark_attendance(stud_id, status):
    cursor.execute(
        "UPDATE students SET status=%s WHERE id=%s",
        (status, stud_id)
    )
    db.commit()
    return redirect(url_for('staff_view'))


@app.route('/assign_test', methods=['POST'])
def assign_test():

    batch = request.form['batch']
    title = request.form['title']
    questions = request.form['questions']
    end_time = request.form['end_time']

    # 1️⃣ insert test
    cursor.execute(
        "INSERT INTO tests (batch, title, questions, end_datetime) VALUES (%s,%s,%s,%s)",
        (batch, title, questions, end_time)
    )
    db.commit()

    test_id = cursor.lastrowid  # 🔥 important

    # 2️⃣ get all students from that batch
    cursor.execute(
        "SELECT id FROM students WHERE batch = %s",
        (batch,)
    )
    students = cursor.fetchall()

    # 3️⃣ assign test to each student
    for s in students:
        cursor.execute(
            "INSERT INTO student_tests (student_id, test_id) VALUES (%s,%s)",
            (s[0], test_id)
        )

    db.commit()

    flash("Test assigned successfully")
    return redirect(url_for('staff_view', batch=batch))


# uploaded file review panna use pandrom

@app.route('/review_assignments')
def review_assignments():

    if 'name' not in session:
        return redirect(url_for('login'))

    cursor.execute("""
        SELECT
            s.student_name,
            s.student_id,
            s.batch,
            t.title,
            st.file_path,
            st.submitted_at,
            st.status
        FROM student_tests st
        JOIN students s ON st.student_id = s.id
        JOIN tests t ON st.test_id = t.id
        WHERE st.file_path IS NOT NULL
        ORDER BY st.submitted_at DESC
    """)

    reviews = cursor.fetchall()

    return render_template(
        'staffview.html',
        name=session['name'],
        reviews=reviews,
        selected_batch=request.args.get('batch', 'Batch 1')
    )
@app.route('/update_review', methods=['POST'])
def update_review():
    st_id = request.form['st_id']
    status = request.form['status']
    marks = request.form['marks']
    review = request.form['review']

    cursor.execute("""
        UPDATE student_tests
        SET status=%s, marks=%s, staff_review=%s
        WHERE id=%s
    """, (status, marks, review, st_id))

    db.commit()
    return redirect(url_for('staff_view'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))  # welcome page


if __name__ == '__main__':
    app.run(debug=True)
