from typing import Any, TypedDict

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from slackbot.config import Settings

settings = Settings()
app = App(token=settings.slack_bot_token)


class SlackEvent(TypedDict):
    channel: str
    text: str
    ts: int


@app.event("app_mention")
def handle_mention(event: SlackEvent, say: Any, client: Any) -> None:
    try:
        client.reactions_add(
            channel=event["channel"],
            name=settings.slack_reaction_acknowledged,
            timestamp=event["ts"],
        )

        # incoming_message = event.get("text", "")

        say(text="I heard you! (LLM integration coming in Milestone 2)", thread_ts=event["ts"])

        client.reactions_add(
            channel=event["channel"],
            name=settings.slack_reaction_handled,
            timestamp=event["ts"],
        )
    except Exception:
        client.reactions_add(
            channel=event["channel"],
            name=settings.slack_reaction_error,
            timestamp=event["ts"],
        )


if __name__ == "__main__":
    handler = SocketModeHandler(app, settings.slack_app_token)
    print("Running...")
    handler.start()  # type: ignore[no-untyped-call]
