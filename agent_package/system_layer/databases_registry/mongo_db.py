import datetime
import os

import certifi
from dotenv import load_dotenv
from pymongo import DESCENDING, MongoClient
from pymongo.errors import ConnectionFailure
from pymongo.server_api import ServerApi

load_dotenv()


class MongoDB:

    def __init__(
        self,
        db_name: str,
        MONGO_DB_USER: str,
        MONGO_DB_PASS: str,
        MONGO_DB_REST_URL: str,
    ):
        """
        Initializes the MongoDB helper class.
        :param db_name: Database name.
        :param collection_name: Collection name.
        """
        uri = f"mongodb+srv://{MONGO_DB_USER}:{MONGO_DB_PASS}{MONGO_DB_REST_URL}"
        self.client = MongoClient(
            uri, server_api=ServerApi("1"), tlsCAFile=certifi.where()
        )

        # Check connection
        try:
            self.client.admin.command("ping")
            print("Connected to MongoDB")
        except ConnectionFailure as e:
            print("Could not connect to MongoDB", e)
        self.db = self.client[db_name]

    def insert_document(self, collection_name: str, document: dict):
        """
        Inserts a single document into the collection.
        :param collection_name:
        :param document: Dictionary representing the document.
        :return: Inserted ID.
        """
        result = self.db[collection_name].insert_one(document)
        return result.inserted_id

    def insert_many_documents(self, collection_name: str, documents: list):
        """
        Inserts multiple documents into the collection.
        :param documents: List of dictionaries representing documents.
        :return: List of inserted IDs.
        """
        result = self.db[collection_name].insert_many(documents)
        return result.inserted_ids

    def find_document(self, collection_name: str, query: dict):
        """
        Finds a single document matching the query.
        :param query: Dictionary representing the query.
        :return: Matching document or None if not found.
        """
        return self.db[collection_name].find_one(query)

    def find_documents(self, collection_name: str, query: dict, limit: int = 0):
        """
        Finds multiple documents matching the query.
        :param query: Dictionary representing the query.
        :param limit: Limit the number of documents returned (default is 0, meaning no limit).
        :return: List of matching documents.
        """
        return list(self.db[collection_name].find(query).limit(limit))

    def find_sorted_documents(
        self, collection_name: str, query: dict, limit: int = 0, skip=0
    ):

        return list(
            self.db[collection_name]
            .find(query)
            .sort("date_posted", DESCENDING)
            .skip(skip)
            .limit(limit)
        )

    def update_document(self, collection_name: str, query: dict, update_data: dict):
        """
        Updates a single document that matches the query.
        :param query: Dictionary representing the query.
        :param update_data: Dictionary representing the fields to update.
        :return: The updated document.
        """
        result = self.db[collection_name].update_one(query, {"$set": update_data})
        return result.modified_count

    def update_words_count(
        self,
        collection_name: str,
        object_id,
        correct_count_increase_rate,
        incorrect_count_increase_rate,
    ):
        update_query = {
            "$inc": {
                "correct_count": correct_count_increase_rate,
                "incorrect_count": incorrect_count_increase_rate,
            },
            "$set": {"last_shown": datetime.datetime.now()},
        }
        self.db[collection_name].update_one(
            {"_id": object_id}, update_query, upsert=True
        )

    def delete_document(self, collection_name: str, query: dict):
        """
        Deletes a single document matching the query.
        :param query: Dictionary representing the query.
        :return: Number of documents deleted.
        """
        result = self.db[collection_name].delete_one(query)
        return result.deleted_count

    def delete_documents(self, collection_name: str, query: dict):
        """
        Deletes multiple documents matching the query.
        :param query: Dictionary representing the query.
        :return: Number of documents deleted.
        """
        result = self.db[collection_name].delete_many(query)
        return result.deleted_count

    def count_documents(self, collection_name: str, query: dict = {}):
        """
        Counts the number of documents in the collection that match the query.
        :param query: Dictionary representing the query.
        :return: Number of matching documents.
        """
        return self.db[collection_name].count_documents(query)

    def get_max_id(self, collection_name: str, query: dict):
        max_id_doc = self.db[collection_name].find(query).sort("_id", -1).limit(1)
        try:
            max_id = max_id_doc.next()["_id"] if max_id_doc.alive else 0
        except:
            max_id = 0
        return max_id

    def get_randomly_entries(
        self, collection_name: str, number_of_entries: int, additional_filter: dict = {}
    ):
        pipeline = [
            {"$match": additional_filter},  # Apply the filter
            {"$sample": {"size": number_of_entries}},  # Fetch random entries
        ]
        results = self.db[collection_name].aggregate(pipeline)
        return results

    def get_least_weight_elements(self, collection_name: str, telegram_id: int) -> list:

        weight_factor = 1  # Factor for correct answers
        penalty_factor = 2  # Factor for incorrect answers
        recency_weight = 0.5  # Factor for recency (higher is more important)

        pipeline = [
            {
                "$addFields": {
                    "score": {
                        "$subtract": [
                            {"$multiply": ["$correct_count", weight_factor]},
                            {"$multiply": ["$incorrect_count", penalty_factor]},
                        ]
                    }
                }
            },
            {
                "$addFields": {
                    "score": {
                        "$add": [
                            "$score",
                            {
                                "$divide": [
                                    recency_weight,
                                    {
                                        "$add": [
                                            {
                                                "$subtract": [
                                                    datetime.datetime.now(),
                                                    "$last_shown",
                                                ]
                                            },
                                            1,
                                        ]
                                    },
                                ]
                            },
                        ]
                    }
                }
            },
            {
                "$match": {
                    "delete_status": False,  # Only include documents where delete_status is False
                    "telegram_id": telegram_id,  # Filter by the specific Telegram ID
                }
            },
            {"$sort": {"score": 1}},  # Sort by score in ascending order (minimum first)
            {"$limit": 4},  # Limit to top 10 words
            {
                "$project": {
                    "_id": 1,
                    "original_text": 1,
                    "translated_text": 1,
                    "score": 1,
                    "usage_examples": 1,
                    "synonyms_in_output_language": 1,
                    "input_language": 1,
                    "output_language": 1,
                    "telegram_id": 1,  # Add telegram_id to check if it's matching
                    "delete_status": 1,
                }
            },
        ]

        # Run aggregation pipeline
        top_words = list(self.db[collection_name].aggregate(pipeline))
        return top_words

    def close_connection(self):
        """
        Closes the MongoDB connection.
        """
        self.client.close()
