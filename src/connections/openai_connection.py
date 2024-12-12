import os
from dotenv import load_dotenv, set_key
from src.connections.base_connection import BaseConnection
from src.helpers import print_h_bar
import openai
from openai import OpenAI

class OpenAIConnection(BaseConnection):
    def __init__(self, model="gpt-3.5-turbo"):
        super().__init__()
        self.model = model
        self.actions={
            "generate-text": {
                "func": self.generate_text,
                "args": {"prompt": "str", "system_prompt": "str"}
            },
            "check-model": {
                "func": self.check_model,
                "args": {}
            },
            "set-model": {
                "func": self.set_model,
                "args": {"model": "str"}
            }
        }

    def configure(self):
        """Sets up OpenAI API authentication"""
        print("\n🤖 OPENAI API SETUP")

        # Check if already configured
        if self.is_configured(verbose=False):
            print("\nOpenAI API is already configured.")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return

        # Get API key
        print("\n📝 To get your OpenAI API credentials:")
        print("1. Go to https://platform.openai.com/account/api-keys")
        print("2. Create a new project or open an exiting one.")
        print("3. In your project settings, navigate to the API keys section and create a new API key")
        api_key = input("Enter your OpenAI API key: ")

        try:
            # Create .env file if it doesn't exist
            if not os.path.exists('.env'):
                with open('.env', 'w') as f:
                    f.write('')

            # Save API key to .env file
            set_key('.env', 'OPENAI_API_KEY', api_key)

            print("\n✅ OpenAI API configuration successfully saved!")
            print("Your API key has been stored in the .env file.")

        except Exception as e:
            print(f"\n❌ An error occurred during setup: {str(e)}")
            return

    def is_configured(self, verbose=True) -> bool:
        """Checks if OpenAI API key is configured and valid"""
        if not os.path.exists('.env'):
            return False

        try:
            # Load env file variables
            load_dotenv()
            api_key = os.getenv('OPENAI_API_KEY')

            # Check if values present
            if not api_key:
                return False

            # Initialize the client
            client = OpenAI(api_key=api_key)
            
            # Try to make a minimal API call to validate the key
            response = client.models.list()
            
            # If we get here, the API key is valid
            return True
            
        except Exception as e:
            if verbose:
                print("❌ There was an error validating your OpenAI credentials:", e)
            return False

    def perform_action(self, action_name, **kwargs):
        """Implementation of abstract method from BaseConnection"""
        if action_name in self.actions:
            return self.actions[action_name]["func"](**kwargs)
        raise Exception(f"Unknown action: {action_name}")

    def generate_text(self, prompt : str="Hello!", system_prompt : str="You are a helpful assistant.", **kwargs):
        # Initialize the client
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Make the API call
        completion = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        )

        # Return the response
        response_message = completion.choices[0].message.content
        return response_message

    def check_model(self, **kwargs):
        return self.model

    def set_model(self, model="DELETE THIS", **kwargs):
        # TODO: Remove model prefilled value, pass model as argument
        try:
            # Make sure model exists
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

            response = client.models.retrieve(model=model)

            # If we get here, the model exists
            self.model = model
            return "\nModel set to: " + self.model
        except Exception as e:
            return "\nError setting model: " + str(e)