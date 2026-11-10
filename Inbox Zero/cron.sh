#!/usr/bin/env bash
# Calls the scheduled endpoints of Inbox Zero, as the "cron" service of the
# upstream docker-compose.yml does. tests/test_app.py compares this table
# with the Compose file of the pinned commit.
set -uo pipefail

readonly WEB_URL="http://127.0.0.1:3000"

# interval in seconds, delay before the first run, path
readonly JOBS="
900 0 /api/cron/scheduled-actions
900 0 /api/cron/automation-jobs
3600 0 /api/follow-up-reminders
1800 0 /api/resend/digest/all
900 0 /api/meeting-briefs
60 0 /api/imap/poll
300 0 /api/meeting-recorder/schedule
21600 0 /api/watch/all
86400 300 /api/cron/reasoning-retention
86400 300 /api/cron/mobile-push-retention
86400 300 /api/cron/email-send-operation-retention
86400 300 /api/cron/draft-cleanup
86400 300 /api/cron/label-cleanup
86400 300 /api/resend/inbox-health/all
604800 300 /api/resend/summary/all
"

until curl --fail --silent --output /dev/null "${WEB_URL}/api/health"; do
    sleep 5
done
printf '[INFO] Scheduler started.\n'

while read -r interval delay path; do
    [[ -n "${path}" ]] || continue
    (
        sleep "${delay}"
        while true; do
            curl --fail --silent --show-error --output /dev/null --max-time 900 \
                --header "Authorization: Bearer ${CRON_SECRET}" "${WEB_URL}${path}" \
                || printf '[WARN] Scheduled request %s failed.\n' "${path}" >&2
            sleep "${interval}"
        done
    ) &
done <<<"${JOBS}"

wait
