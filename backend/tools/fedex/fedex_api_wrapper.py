from token_service import get_token_for_provider, refresh_token_for_provider
import os

def _request_with_auto_refresh(method, url, headers=None, **kwargs):
    provider = "fedex"
    hdrs = dict(headers or {})
    tok = get_token_for_provider(provider)
    if tok and isinstance(tok, dict) and tok.get("access_token"):
        hdrs.setdefault("Authorization", f"Bearer {tok['access_token']}")
    resp = requests.request(method.upper(), url, headers=hdrs, **kwargs)
    if getattr(resp, "status_code", None) in (401, 403):
        new_tok = refresh_token_for_provider(provider)
        if new_tok and new_tok.get("access_token"):
            hdrs["Authorization"] = f"Bearer {new_tok['access_token']}"
        resp = requests.request(method.upper(), url, headers=hdrs, **kwargs)
    return resp

import requests
from dotenv import load_dotenv

load_dotenv()

class FedExWrapper:
    def __init__(self):
        self.token_url = "https://apis-sandbox.fedex.com/oauth/token"
        self.shipment_url = "https://apis-sandbox.fedex.com/ship/v1/shipments"
        self.client_id = os.getenv("FEDEX_CLIENT_ID")
        self.client_secret = os.getenv("FEDEX_CLIENT_SECRET")
        self.account_number = os.getenv("FEDEX_ACCOUNT_NUMBER")
        self.token = self.get_token()

    def get_token(self):
        print("Requesting FedEx token...")
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        response = _request_with_auto_refresh('post', self.token_url, data=data, auth=(self.client_id, self.client_secret))
        if response.status_code == 200:
            print(" Token acquired.")
            return response.json()["access_token"]
        else:
            print("Failed to get FedEx token.")
            raise Exception(f"{response.status_code} - {response.text}")

    def create_shipment(self, personName: str = None, phoneNumber: str = None, streetLine: str = None, city: str = None, stateOrProvince: str = None, postalCode: str = None, countryCode: str = None):
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "x-locale": "en_US",
        }
        
        # payload = None
        
        if not personName or not phoneNumber or not streetLine or not city or not stateOrProvince or not postalCode or not countryCode:

            payload = {
                "labelResponseOptions": "URL_ONLY",
                "accountNumber": {"value": self.account_number},
                "requestedShipment": {
                    "shipDatestamp": "2025-08-01",
                    "pickupType": "DROPOFF_AT_FEDEX_LOCATION",
                    "serviceType": "FEDEX_GROUND",
                    "packagingType": "YOUR_PACKAGING",
                    "shipper": {
                        "contact": {
                            "personName": "Madison Doe",
                            "companyName": "Chai Corner",
                            "phoneNumber": "1234567890"
                        },
                        "address": {
                            "streetLines": ["1234 Main St"],
                            "city": "Collierville",
                            "stateOrProvinceCode": "TN",
                            "postalCode": "38017",
                            "countryCode": "US"
                        }
                    },
                    "recipients": [{
                        "contact": {
                            "personName": "Smith Doe",
                            "companyName": "Receiver Corp 3",
                            "phoneNumber": "0987654321"
                        },
                        "address": {
                            "streetLines": ["5678 Market St"],
                            "city": "Memphis",
                            "stateOrProvinceCode": "TN",
                            "postalCode": "38116",
                            "countryCode": "US"
                        }
                    }],
                    "shippingChargesPayment": {
                        "paymentType": "SENDER"
                    },
                    "labelSpecification": {
                        "imageType": "PDF",
                        "labelStockType": "PAPER_4X6"
                    },
                    "requestedPackageLineItems": [{
                        "weight": {"units": "LB", "value": 2},
                        "dimensions": {"length": 10, "width": 5, "height": 5, "units": "IN"}
                    }]
                }
            }
        else:
            payload = {
                "labelResponseOptions": "URL_ONLY",
                "accountNumber": {"value": self.account_number},
                "requestedShipment": {
                    "shipDatestamp": "2025-08-01",
                    "pickupType": "DROPOFF_AT_FEDEX_LOCATION",
                    "serviceType": "FEDEX_GROUND",
                    "packagingType": "YOUR_PACKAGING",
                    "shipper": {
                        "contact": {
                            "personName": "Madison Doe",
                            "companyName": "Chai Corner",
                            "phoneNumber": "1234567890"
                        },
                        "address": {
                            "streetLines": ["1234 Main St"],
                            "city": "Collierville",
                            "stateOrProvinceCode": "TN",
                            "postalCode": "38017",
                            "countryCode": "US"
                        }
                    },
                    "recipients": [{
                        "contact": {
                            "personName": personName,
                            "companyName": "Receiver Corp 3",
                            "phoneNumber": phoneNumber
                        },
                        "address": {
                            "streetLines": [streetLine],
                            "city": city,
                            "stateOrProvinceCode": stateOrProvince,
                            "postalCode": postalCode,
                            "countryCode": countryCode
                        }
                    }],
                    "shippingChargesPayment": {
                        "paymentType": "SENDER"
                    },
                    "labelSpecification": {
                        "imageType": "PDF",
                        "labelStockType": "PAPER_4X6"
                    },
                    "requestedPackageLineItems": [{
                        "weight": {"units": "LB", "value": 2},
                        "dimensions": {"length": 10, "width": 5, "height": 5, "units": "IN"}
                    }]
                }
            }

        try:
            response = _request_with_auto_refresh('post', self.shipment_url, headers=headers, json=payload)
            json_data = response.json()

            label_url = None
            tracking_number = None
            try:
                label_url = json_data["output"]["transactionShipments"][0]["pieceResponses"][0]["packageDocuments"][0]["url"]
                tracking_number = json_data["output"]["transactionShipments"][0]["masterTrackingNumber"]
            except Exception:
                pass  # label might not be available in error case

            if response.status_code == 200:
                print("Shipment Created")
                return {
                    "success": True,
                    "label_url": label_url,
                    "tracking_number": tracking_number,
                    "error": None
                }
            else:
                print("Shipment Failed:", response.status_code)
                return {
                    "success": False,
                    "label_url": label_url,
                    "tracking_number": tracking_number,
                    "error": json_data.get("errors", "Unknown error")
                }

        except Exception as e:
            print(" Exception during shipment:", str(e))
            return {
                "success": False,
                "label_url": None,
                "tracking_number": None,
                "error": str(e)
            }