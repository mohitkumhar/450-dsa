from app.utils import trigger_discord_event

def check_leaderboard_entry(user_id, user_name, new_rank, c_score):
    """Check if a user entered top 10 and trigger Discord notification."""
    if new_rank <= 10:
        trigger_discord_event("leaderboard_top10", {
            "rank": new_rank,
            "user_name": user_name,
            "c_score": c_score,
            "user_id": user_id
        })