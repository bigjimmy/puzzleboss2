from __future__ import print_function
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/admin.directory.user"]


def main():

    # Run this from a terminal to trigger auth token creation with google for puzzleboss.

    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("admintoken.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=9999)
        # Save the credentials for the next run
        with open("admintoken.json", "w") as token:
            token.write(creds.to_json())

    service = build("admin", "directory_v1", credentials=creds)
    print("Authenticated.")

    # Call the Admin SDK Directory API
    print("Getting the first 10 users in the domain")
    results = (
        service.users()
        .list(customer="my_customer", maxResults=10, orderBy="email")
        .execute()
    )
    users = results.get("users", [])

    if not users:
        print("No users in the domain.")
    else:
        print("Users:")
        for user in users:
            print(u"{0} ({1})".format(user["primaryEmail"], user["name"]["fullName"]))


if __name__ == "__main__":
    main()
