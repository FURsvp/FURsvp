pkill gunicorn
pkill python3

git pull

# Check if git pull was successful
if [ $? -ne 0 ]; then
    echo "Git pull failed. Exiting startup script." >&2
    exit 1
fi

PYTHON_PATH="python3"
MANAGE_PY="./manage.py"

"$PYTHON_PATH" "$MANAGE_PY" makemigrations events
"$PYTHON_PATH" "$MANAGE_PY" makemigrations users
"$PYTHON_PATH" "$MANAGE_PY" makemigrations
"$PYTHON_PATH" "$MANAGE_PY" migrate
"$PYTHON_PATH" "$MANAGE_PY" migrate users
"$PYTHON_PATH" "$MANAGE_PY" migrate events
"$PYTHON_PATH" "$MANAGE_PY" createcachetable
"$PYTHON_PATH" "$MANAGE_PY" collectstatic


echo "Done!"