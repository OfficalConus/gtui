#!/usr/bin/env python3
import os, json, base64, webbrowser, concurrent.futures
from pathlib import Path
from datetime import datetime
from email.message import EmailMessage
from email.utils import parsedate_to_datetime

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.theme import Theme
from textual.widgets import (
    Header, Footer, Button, ListView, ListItem, Static,
    Input, TextArea, Rule
)
from textual.binding import Binding
from textual.message import Message

import httplib2
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google_auth_httplib2 import AuthorizedHttp

DATA_DIR = Path.home() / ".gmail-tui"
DATA_DIR.mkdir(exist_ok=True)
CLIENT_SECRET = DATA_DIR / "client_secret.json"
TOKEN_FILE = DATA_DIR / "token.json"
THEME_FILE = DATA_DIR / "theme.json"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

COMPACT_W = 100

B = "#1e1e2e"
SURF = "#181825"
PNL = "#11111b"
TEXT = "#cdd6f4"
BOOST = "#585b70"

# Nerd Font icon codepoints
I = {
    "menu":"\uf0c9","refresh":"\uf01e","compose":"\uf044","logout":"\uf08b",
    "back":"\uf060","send":"\uf1d9","close":"\uf00d","done":"\uf00c",
    "inbox":"\uf01c","sent":"\uf1d9","starred":"\uf006","draft":"\uf0f6","trash":"\uf014",
    "themes":"\uf013","switch":"\uf007","setup":"\uf013","login":"\uf090","mail":"\uf003",
}

THEMES = {
    "mocha-mauve":    {"p": "#cba6f7", "s": "#b4befe", "l": "Mocha Mauve"},
    "mocha-blue":     {"p": "#89b4fa", "s": "#b4befe", "l": "Mocha Blue"},
    "mocha-pink":     {"p": "#f5c2e7", "s": "#f2cdcd", "l": "Mocha Pink"},
    "mocha-green":    {"p": "#a6e3a1", "s": "#94e2d5", "l": "Mocha Green"},
    "mocha-peach":    {"p": "#fab387", "s": "#f9e2af", "l": "Mocha Peach"},
    "mocha-red":      {"p": "#f38ba8", "s": "#eba0ac", "l": "Mocha Red"},
    "mocha-teal":     {"p": "#94e2d5", "s": "#89dceb", "l": "Mocha Teal"},
    "mocha-rosewater":{"p": "#f5e0dc", "s": "#f2cdcd", "l": "Mocha Rosewater"},
    "mocha-yellow":   {"p": "#f9e2af", "s": "#fab387", "l": "Mocha Yellow"},
    "matrix":         {"p": "#00ff41", "s": "#00cc33", "l": "Matrix"},
}

KEYS = list(THEMES.keys())
HTTP_TIMEOUT = 120

def gmail_service(creds):
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    h = httplib2.Http(timeout=HTTP_TIMEOUT)
    ah = AuthorizedHttp(creds, http=h)
    return build("gmail", "v1", http=ah, cache_discovery=False)




def load_theme():
    try:
        return json.loads(THEME_FILE.read_text()).get("theme", "mocha-mauve")
    except:
        return "mocha-mauve"

def save_theme(n):
    THEME_FILE.write_text(json.dumps({"theme": n}))


CSS = """\

Screen { background: $surface; color: $text; }

#login-container { align: center middle; width: 100%; height: 100%; }
#login-box { align: center middle; width: auto; height: auto; border: solid $primary; background: $panel; padding: 2 4; }
#title { text-style: bold; text-align: center; height: 3; color: $primary; }
#subtitle { text-align: center; color: $text-muted; }
#login-buttons { align: center middle; height: auto; margin: 1 0 0 0; }
#login-btn, #setup-btn { margin: 0 1; }
#status { text-align: center; margin: 1 0; }

#sidebar { width: 22; border-right: solid $primary; padding: 1; background: $surface; }
#sidebar Button { width: 100%; margin: 0 0 1 0; }
.folder-btn { background: $surface; color: $text; }
.folder-btn:hover { background: $boost; }

#main-area { width: 1fr; height: 100%; }
#toolbar { height: 3; padding: 0 1; border-bottom: solid $primary-darken-2; }
#toolbar Button { margin: 0 1 0 0; }
#email-count { content-align: right middle; color: $text-muted; width: 1fr; }
#email-list { height: 1fr; border: none; }
#email-list ListItem { padding: 0 1; }
#email-list ListItem:hover { background: $boost; }
#loading-status { height: 1; padding: 0 1; color: $text-muted; }

#email-container { padding: 1 2; height: 100%; }
#email-subject { text-style: bold; height: 3; }
#email-body { height: 1fr; padding: 1 0; }

#compose-container { padding: 1 2; height: 100%; }
#compose-title { text-style: bold; height: 3; color: $primary; }
#compose-buttons { height: 3; margin: 1 0; }
#compose-buttons Button { margin: 0 1 0 0; }

Button.-primary { background: $primary; color: $background; }
Button.-primary:hover { background: $secondary; }
Button.-error { background: $error; color: $background; }
Button.-default { background: $primary-darken-2; color: $text; }
Button.-default:hover { background: $boost; }

Static { color: $text; }
Input { background: $boost; color: $text; border: solid $primary-darken-2; }
Input:focus { border: solid $primary; }
TextArea { background: $boost; color: $text; border: solid $primary-darken-2; }
TextArea:focus { border: solid $primary; }

Header { background: $panel; color: $text; }
Footer { background: $panel; color: $text-muted; }
Rule { background: $primary-darken-2; }
#view-title { text-style: bold; padding: 0 1; height: 1; }
#theme-grid { layout: grid; grid-size: 4; grid-gutter: 1; padding: 1 2; }
.theme-btn { min-width: 14; }
"""


class SetupGuideScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with ScrollableContainer():
            yield Static("""
[bold yellow]Setting up Gmail API Access[/]

You need OAuth 2.0 credentials to use the Gmail API.

[bold]Step 1:[/] Go to Google Cloud Console
  https://console.cloud.google.com/

[bold]Step 2:[/] Create a new project or select existing

[bold]Step 3:[/] Enable the Gmail API
  APIs & Services -> Library -> Search "Gmail API" -> Enable

[bold]Step 4:[/] Create OAuth consent screen
  APIs & Services -> OAuth consent screen
  User Type: External -> Create
  App name: "Gmail TUI" (or anything)
  Add scopes: ../auth/gmail.readonly, ../auth/gmail.send, ../auth/gmail.modify
  Add test users: your gmail address

[bold]Step 5:[/] Create OAuth 2.0 Client ID
  APIs & Services -> Credentials -> Create Credentials
  OAuth client ID -> Application type: Desktop app
  Name: "Gmail TUI CLI"
  Download JSON -> save as:

[bold underline]$HOME/.gmail-tui/client_secret.json[/]

[bold]Step 6:[/] Come back and click Login with Google

Make sure you add your email as a Test User in OAuth consent screen!
""")
            yield Button(f" {I['back']}  Back", id="back-btn", variant="primary")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back-btn":
            self.app.pop_screen()


class ThemeScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            yield Static("[bold]Select Theme[/]", id="theme-title")
            with ScrollableContainer(id="theme-grid"):
                cur = self.app.theme
                for k in KEYS:
                    t = THEMES[k]
                    cls = "theme-btn -selected" if cur == k else "theme-btn"
                    yield Button(f"  {t['l']}  ", id=f"t-{k}", classes=cls,
                                 variant="primary" if cur == k else "default")
            yield Button(f" {I['done']}  Done", id="done-btn", variant="primary")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        b = event.button.id
        if b == "done-btn":
            self.app.pop_screen()
        elif b and b.startswith("t-"):
            n = b[2:]
            save_theme(n)
            self.app.theme = n
            for btn in self.query(".theme-btn"):
                btn.classes = "theme-btn"
                btn.variant = "default"
            w = self.query_one(f"#t-{n}")
            w.classes = "theme-btn -selected"
            w.variant = "primary"


class LoginScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="login-container"):
            with Vertical(id="login-box"):
                yield Static("[bold]GTUI[/]", id="title")
                yield Static("Gmail TUI client", id="subtitle")
                yield Static("", id="status")
                with Horizontal(id="login-buttons"):
                    yield Button(f" {I['login']}  Login", id="login-btn", variant="primary")
                    yield Button(f" {I['setup']}  Setup", id="setup-btn", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        if not CLIENT_SECRET.exists():
            self.query_one("#status").update("[yellow]No OAuth credentials found[/]")
        elif not TOKEN_FILE.exists():
            self.query_one("#status").update("[cyan]Click Login to authorize[/]")
        else:
            try:
                c = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
                if c and c.valid:
                    self.dismiss(c)
                    return
            except:
                pass
            self.query_one("#status").update("[cyan]Click Login to re-authorize[/]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        b = event.button.id
        if b == "login-btn":
            self.do_login()
        elif b == "setup-btn":
            self.app.push_screen(SetupGuideScreen())

    def do_login(self) -> None:
        if not CLIENT_SECRET.exists():
            self.query_one("#status").update("[red]Create OAuth credentials first![/]")
            self.app.push_screen(SetupGuideScreen())
            return
        self.query_one("#status").update("[cyan]Opening browser...[/]")
        self.start_auth()

    @work(thread=True)
    def start_auth(self) -> None:
        try:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
            c = flow.run_local_server(open_browser=True)
            TOKEN_FILE.write_text(c.to_json())
            self.app.call_from_thread(self.done, c)
        except Exception as e:
            self.app.call_from_thread(lambda: self.query_one("#status").update(f"[red]{e}[/]"))

    def done(self, c):
        self.query_one("#status").update("[green]Logged in![/]")
        self.dismiss(c)


class EmailListItem(ListItem):
    def __init__(self, msg_id: str, sender: str, subject: str, snippet: str, date: str, unread: bool):
        self.msg_id = msg_id
        p = "[bold]" if unread else ""
        super().__init__(Static(f"{p}{sender:<25} {subject:<50} [dim]{date}[/]"))


class ComposeScreen(Screen):
    class EmailSent(Message):
        def __init__(self, to: str, subject: str):
            self.to, self.subject = to, subject
            super().__init__()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="compose-container"):
            yield Static("[bold]Compose[/]", id="compose-title")
            yield Static("To:")
            yield Input(placeholder="recipient@example.com", id="to-input")
            yield Static("Subject:")
            yield Input(placeholder="Subject", id="subj-input")
            yield Static("Message:")
            yield TextArea(id="msg-body", language=None)
            with Horizontal(id="compose-buttons"):
                yield Button(f" {I['send']}  Send", id="send-btn", variant="primary")
                yield Button(f" {I['close']}  Cancel", id="cancel-btn", variant="default")
            yield Static("", id="compose-status")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#msg-body").styles.height = "12"
        self.query_one("#to-input").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send-btn":
            to = self.query_one("#to-input").value.strip()
            subj = self.query_one("#subj-input").value.strip()
            body = self.query_one("#msg-body").text
            self.send_it(to, subj, body)
        else:
            self.app.pop_screen()

    @work(thread=True)
    def send_it(self, to: str, subj: str, body: str) -> None:
        if not to:
            self.app.call_from_thread(lambda: self.query_one("#compose-status").update("[red]To required[/]"))
            return
        try:
            from email.message import EmailMessage
            m = EmailMessage()
            m.set_content(body)
            m["To"] = to
            m["Subject"] = subj
            raw = base64.urlsafe_b64encode(m.as_bytes()).decode()
            svc = gmail_service(self.app.credentials)
            svc.users().messages().send(userId="me", body={"raw": raw}).execute()
            self.app.call_from_thread(self.app.pop_screen)
            self.app.post_message(ComposeScreen.EmailSent(to, subj))
        except Exception as e:
            self.app.call_from_thread(lambda: self.query_one("#compose-status").update(f"[red]{e}[/]"))


class EmailScreen(Screen):
    def __init__(self, mid, subj, sender, date, body):
        self.mid = mid; self.esubj = subj; self.esender = sender
        self.edate = date; self.ebody = body
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="email-container"):
            yield Static(f"[bold]{self.esubj}[/]", id="email-subject")
            yield Static(f"From: {self.esender}")
            yield Static(f"Date: {self.edate}")
            yield Rule()
            yield Static(self.ebody or "[dim](no content)[/]", id="email-body")
            yield Button(f" {I['back']}  Back", id="back-btn", variant="default")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back-btn":
            self.app.pop_screen()


class MainScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="sidebar", classes="column"):
                yield Static("[bold]Folders[/]", id="folder-title")
                for ik, fid in self.FOLDERS:
                    yield Button(f" {I[ik]}  {fid.title()}", id=f"f-{fid}", classes="folder-btn")
            with Vertical(id="main-area", classes="column"):
                with Horizontal(id="toolbar"):
                    yield Button(f" {I['menu']}  Menu", id="menu-btn", variant="default")
                    yield Button(f" {I['refresh']}  Refresh", id="refresh-btn", variant="primary")
                    yield Button(f" {I['compose']}  Compose", id="compose-btn", variant="primary")
                    yield Button(f" {I['logout']}  Logout", id="logout-btn", variant="error")
                    yield Static("", id="email-count")
                yield Static("[bold]Inbox[/]", id="view-title")
                yield ListView(id="email-list")
                yield Static("", id="loading-status")
        yield Footer()

    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("c", "compose", "Compose"),
        Binding("q", "quit_app", "Quit"),
    ]

    FOLDERS = [("inbox","INBOX"),("sent","SENT"),("starred","STARRED"),
               ("draft","DRAFTS"),("trash","TRASH")]
    TOOLBTNS = [("menu-btn","Menu","menu"),("refresh-btn","Refresh","refresh"),
                ("compose-btn","Compose","compose"),("logout-btn","Logout","logout")]

    def update_compact(self):
        c = self.app.size.width < COMPACT_W
        if getattr(self, '_c', None) == c: return
        self._c = c
        for bid, txt, ik in self.TOOLBTNS:
            try: self.query_one(f"#{bid}").label = f" {I[ik]}" if c else f" {I[ik]}  {txt}"
            except: pass
        for ik, fid in self.FOLDERS:
            try: self.query_one(f"#f-{fid}").label = f" {I[ik]}" if c else f" {I[ik]}  {fid.title()}"
            except: pass
        try: self.query_one("#sidebar").styles.width = 8 if c else 22
        except: pass
        try: self.query_one("#folder-title").display = not c
        except: pass

    def on_resize(self) -> None:
        self.update_compact()

    def on_mount(self) -> None:
        self.folder = "INBOX"
        self.update_compact()
        self.fetch_mail()

    def fetch_one(self, mid, svc):
        d = svc.users().messages().get(userId="me", id=mid, format="metadata",
            metadataHeaders=["From","Subject","Date"]).execute()
        h = {x["name"]: x["value"] for x in d["payload"]["headers"]}
        dr = h.get("Date", "")
        try:
            df = parsedate_to_datetime(dr).strftime("%b %d %H:%M")
        except:
            df = dr[:17]
        return (parsedate_to_datetime(dr) if dr else datetime.min, mid,
                h.get("From","?").split("<")[0].strip().strip('"'),
                h.get("Subject","(no subject)"), d.get("snippet",""), df,
                "UNREAD" in d.get("labelIds", []))

    def fetch_all(self, service, msg_ids):
        items = []
        fail = 0
        for mid in msg_ids:
            try:
                items.append(self.fetch_one(mid, service))
            except:
                fail += 1
        if fail:
            def show_fail():
                self.query_one("#loading-status").update(
                    f"[yellow]{len(items)}/{len(msg_ids)} ({fail} failed)[/]")
            self.app.call_from_thread(show_fail)
        items.sort(key=lambda x: x[0], reverse=True)
        return items

    @work(thread=True)
    def fetch_mail(self) -> None:
        try:
            self.app.call_from_thread(lambda: self.query_one("#email-list").clear())
            self.app.call_from_thread(lambda: self.query_one("#loading-status").update("[cyan]Loading...[/]"))
            if not self.app.credentials:
                raise Exception("Not logged in")
            svc = gmail_service(self.app.credentials)
            lb = [self.folder] if self.folder != "SENT" else ["SENT"]
            res = svc.users().messages().list(userId="me", maxResults=15, labelIds=lb).execute()
            mids = [m["id"] for m in res.get("messages", [])]
            est = res.get("resultSizeEstimate", 0)
            def show_ids():
                self._est = est
                self._mid_count = len(mids)
                self.query_one("#loading-status").update(
                    f"[cyan]{len(mids)} IDs (est {est}), fetching...[/]")
            self.app.call_from_thread(show_ids)
            items = self.fetch_all(svc, mids) if mids else []
            self.app.call_from_thread(self.populate, items)
        except Exception as e:
            self.app.call_from_thread(lambda: self.query_one("#loading-status").update(f"[red]{type(e).__name__}: {e}[/]"))

    def populate(self, items):
        lst = self.query_one("#email-list")
        lst.clear()
        for _, mid, snd, subj, snip, df, unread in items:
            lst.append(EmailListItem(mid, snd, subj, snip, df, unread))
        c = len(items)
        self.query_one("#email-count").update(f" ({c})")
        if c:
            self.query_one("#loading-status").update(f"[green]{c} emails[/]")
        elif hasattr(self, '_est') and self._est > 0:
            self.query_one("#loading-status").update(
                f"[yellow]API reports {self._est} msgs, but all {self._mid_count} fetches failed[/]")
        else:
            self.query_one("#loading-status").update("[yellow]Empty[/]")

    def action_refresh(self):
        self.fetch_mail()

    def action_compose(self):
        self.app.push_screen(ComposeScreen())

    def action_quit_app(self):
        self.app.exit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        b = event.button.id or ""
        if b == "menu-btn":
            self.app.push_screen(MenuScreen())
        elif b == "refresh-btn":
            self.fetch_mail()
        elif b == "compose-btn":
            self.action_compose()
        elif b == "logout-btn":
            TOKEN_FILE.unlink(missing_ok=True)
            self.app.credentials = None
            self.app.switch_screen(LoginScreen())
        elif b.startswith("f-"):
            self.folder = b[2:]
            self.query_one("#view-title").update(f"[bold]{self.folder.title()}[/]")
            self.fetch_mail()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        it = event.item
        if isinstance(it, EmailListItem):
            self.load_email(it)

    @work(thread=True)
    def load_email(self, it: EmailListItem) -> None:
        try:
            svc = gmail_service(self.app.credentials)
            d = svc.users().messages().get(userId="me", id=it.msg_id, format="full").execute()
            h = {x["name"]: x["value"] for x in d["payload"]["headers"]}
            body = self.get_body(d["payload"])
            self.app.call_from_thread(lambda: self.app.push_screen(
                EmailScreen(it.msg_id, h.get("Subject","(no subject)"),
                h.get("From","?"), h.get("Date",""), body)))
        except Exception as e:
            self.app.call_from_thread(lambda: self.query_one("#loading-status").update(f"[red]{e}[/]"))

    def get_body(self, p):
        if "parts" in p:
            for part in p["parts"]:
                if part.get("mimeType") == "text/plain" and part.get("body",{}).get("data"):
                    return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
                if "parts" in part: return self.get_body(part)
        if p.get("body",{}).get("data"):
            return base64.urlsafe_b64decode(p["body"]["data"]).decode("utf-8", errors="replace")
        return "[dim](no text)[/]"

    def on_compose_screen_email_sent(self, m: ComposeScreen.EmailSent) -> None:
        self.query_one("#loading-status").update(f"[green]Sent to {m.to}: {m.subject}[/]")


class MenuScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="login-container"):
            with Vertical(id="login-box"):
                yield Static("[bold]Menu[/]", id="title")
                with Vertical(id="menu-items"):
                    yield Button(f" {I['themes']}  Themes", id="menu-theme", variant="primary")
                    yield Button(f" {I['switch']}  Switch Account", id="menu-switch", variant="default")
                    yield Button(f" {I['logout']}  Logout", id="menu-logout", variant="error")
                yield Button(f" {I['close']}  Close", id="menu-close", variant="default")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        b = event.button.id
        if b == "menu-close":
            self.app.pop_screen()
        elif b == "menu-theme":
            self.app.push_screen(ThemeScreen())
        elif b == "menu-switch":
            TOKEN_FILE.unlink(missing_ok=True)
            self.app.credentials = None
            self.app.switch_screen(LoginScreen())
        elif b == "menu-logout":
            TOKEN_FILE.unlink(missing_ok=True)
            self.app.credentials = None
            self.app.switch_screen(LoginScreen())


class GmailApp(App):
    CSS = CSS
    BINDINGS = [Binding("ctrl+q", "quit", "Quit")]

    def on_mount(self) -> None:
        for k, t in THEMES.items():
            bg = "#0a0a0a" if k == "matrix" else B
            sf = "#0d0d0d" if k == "matrix" else SURF
            pn = "#000000" if k == "matrix" else PNL
            tx = "#00ff41" if k == "matrix" else TEXT
            bs = "#004400" if k == "matrix" else BOOST
            self.register_theme(Theme(
                name=k, dark=True,
                primary=t["p"], secondary=t["s"], accent=t["p"],
                background=bg, surface=sf, panel=pn,
                foreground=tx, boost=bs,
                error="#f38ba8", success="#a6e3a1", warning="#f9e2af",
            ))
        self.theme = load_theme()
        self.credentials = None
        self.push_screen(LoginScreen(), self.on_login)

    def on_login(self, c) -> None:
        if c:
            self.credentials = c
            self.push_screen(MainScreen())

    def action_quit(self):
        self.exit()


if __name__ == "__main__":
    GmailApp().run()
