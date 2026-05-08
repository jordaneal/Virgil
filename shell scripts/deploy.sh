#!/bin/bash
FILE=${1:-/home/jordaneal/scripts/virgil_bot.py}
echo "Checking syntax..."
python3 -c "import ast; ast.parse(open('$FILE').read()); print('OK')"
if [ $? -ne 0 ]; then
    echo "Syntax error — aborting"
    exit 1
fi
echo "Restarting virgil-bot..."
systemctl --user restart virgil-bot
sleep 2
systemctl --user is-active virgil-bot && echo "✅ Virgil is running" || echo "❌ Virgil failed to start"
