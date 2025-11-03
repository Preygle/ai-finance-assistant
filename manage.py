import click
from flask.cli import with_appcontext
from app import create_app, db

app = create_app()

@click.command(name='reset-transactions')
@with_appcontext
def reset_transactions():
    """Drops and recreates the transaction table."""
    try:
        from models import User, Transaction, AIModelStorage, IntegrityProof, TransactionAIFiltered
        # Drop the transaction table
        Transaction.__table__.drop(db.engine)
        # Recreate the transaction table
        db.create_all()
        print("Transaction database reset successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    app.cli.add_command(reset_transactions)
    app.run()
