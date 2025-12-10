from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, create_model

# A flat list of the most common high-level business categories
# often used for drop-down menus or categorization logic.
CATEGORIES = [
    # Accommodation
    "Hotel",
    "Motel",
    "Bed & Breakfast",
    "Resort Hotel",
    "Vacation Rental Agency",
    # Real Estate & Housing
    "Real Estate",
    "Real Estate Agency",
    "Real Estate Agent",
    "Apartment Complex",
    "Condominium Complex",
    "Property Management Company",
    "Commercial Real Estate Agency",
    "Student Housing Center",
    # Food & Dining
    "Restaurant",
    "Cafe",
    "Bar",
    "Bakery",
    "Grocery Store",
    # Health
    "Dentist",
    "Medical Clinic",
    "Hospital",
    "Pharmacy",
    "Physical Therapist",
    # Professional Services
    "Lawyer",
    "Accountant",
    "Marketing Agency",
    "Insurance Agency",
    "Consultant",
    # Trades / Home Services
    "Plumber",
    "Electrician",
    "Locksmith",
    "HVAC Contractor",
    "Landscaper",
    "Roofer",
    # Automotive
    "Car Dealer",
    "Auto Repair Shop",
    "Car Rental Agency",
    "Car Wash",
    "Movie",
    "Cinema",
    "Film",
]


enum_map = {
    name.replace(" & ", "_And_").replace(" ", "_").upper(): name for name in CATEGORIES
}

# 3. Create the Enum class dynamically
# Enum(class_name, dictionary, type=str) creates a StrEnum
CategoryEnum = Enum("CategoryEnum", enum_map, type=str)


class CategoryPrediction(BaseModel):
    category: Optional[List[CategoryEnum]] = Field(
        description="List of matched categories"
    )
    reasoning: str
    # output_structure: str = Field(description="JSON schema string for the expected agent output")


class FinalSynthesis(BaseModel):
    answer: str
    output_structure: BaseModel
