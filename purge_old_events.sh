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

"$PYTHON_PATH" "$MANAGE_PY" delete_old_events

echo "Done!"