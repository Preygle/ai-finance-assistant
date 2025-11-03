"""Test script for AWS Bedrock integration using Claude 3 Sonnet model.

Usage:
    # Set AWS credentials in environment - PowerShell example:
    $env:AWS_ACCESS_KEY_ID = 'your-access-key'
    $env:AWS_SECRET_ACCESS_KEY = 'your-secret-key'
    python test_bedrock_run.py
"""

import boto3
import json

# ---------- CONFIGURATION ----------
REGION = "us-east-1"  # Change if needed
MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"
# ----------------------------------

# Initialize the Bedrock client
bedrock = boto3.client("bedrock-runtime", region_name=REGION)

def calculate_health_score(data):
    """Calculate financial health score based on transaction data."""
    try:
        income = data["summary"]["total_income"]
        expenses = data["summary"]["total_expenses"]
        savings_rate = ((income - expenses) / income) * 100
        
        # Base score calculation (up to 100 points)
        score = min(100, max(0, int(savings_rate)))
        
        # Description based on score
        if score >= 90:
            description = "Excellent financial health! Keep up the great work!"
        elif score >= 70:
            description = "Good financial health. Some room for improvement."
        elif score >= 50:
            description = "Fair financial health. Consider following the recommendations."
        else:
            description = "Financial health needs attention. Focus on saving more."
            
        return score, description
    except Exception as e:
        return 50, "Insufficient data for accurate health score calculation."

def analyze_finances(transaction_data):
    """Analyze financial data using Amazon Bedrock Claude 3 model."""
    
    prompt = f"""Human: You are an expert financial analyst. Based on the following transaction data, analyze the spending patterns and provide insights.

Return ONLY a JSON object with these exact three keys (no other text):
1. patterns: Array of 3-5 clear observations about spending patterns
2. recommendations: Array of 3-5 specific budget recommendations
3. opportunities: Array of 3-5 concrete savings opportunities

Make each point clear, specific, and actionable. Include numbers and percentages where relevant.

Transaction Data:
{json.dumps(transaction_data, indent=2)}

    # Prepare the request body for Claude 3
    body = json.dumps({
        "prompt": prompt,
        "max_tokens": 500,
        "temperature": 0.7,
        "top_p": 1,
        "stop_sequences": ["\n\nHuman:", "\n\nAssistant:"]
    })

    print("🤖 Sending data to Bedrock for analysis...")

    # Invoke the model
    response = bedrock.invoke_model(
        body=body,
        modelId=MODEL_ID,
        accept="application/json",
        contentType="application/json",
    )

    # Parse the response
    response_body = json.loads(response.get("body").read())
    completion = response_body.get("completion", "").strip()

    # Parse the JSON response
    try:
        # Find the first { and last } to extract just the JSON part
        start = completion.find('{')
        end = completion.rfind('}') + 1
        if start >= 0 and end > start:
            json_str = completion[start:end]
            analysis = json.loads(json_str)
            return analysis
        else:
            print("⚠️ Warning: No JSON object found in response")
            return {"error": "No JSON found in response", "raw_output": completion}
    except json.JSONDecodeError:
        print("⚠️ Warning: Could not parse model output as JSON")
        return {"error": "Invalid JSON response", "raw_output": completion}

if __name__ == "__main__":
    # Sample transaction data for testing
    sample_data = {
        "summary": {
            "total_transactions": 150,
            "total_income": 85000.00,
            "total_expenses": 65000.00,
            "top_categories": ["Housing", "Groceries", "Transportation"],
            "time_period": "Last 3 months"
        },
        "recent_transactions": [
            {
                "date": "2025-11-01",
                "amount": 1500.00,
                "category": "Housing",
                "description": "Monthly Rent"
            },
            {
                "date": "2025-11-02",
                "amount": 85.50,
                "category": "Groceries",
                "description": "Whole Foods Market"
            }
        ]
    }

    print("🔄 Running financial analysis...")
    
    try:
        # Get AI insights
        result = analyze_finances(sample_data)
        
        # Calculate health score
        health_score, health_description = calculate_health_score(sample_data)
        
        # Combine all insights
        full_analysis = {
            "patterns": result.get("patterns", []),
            "recommendations": result.get("recommendations", []),
            "opportunities": result.get("opportunities", []),
            "health_score": health_score,
            "health_description": health_description
        }
        
        print("\n✅ Analysis complete!")
        print("\nResults:")
        print(json.dumps(full_analysis, indent=2))
        
        print("\nThis data structure matches your analytics.html template requirements.")
        print("You can now pass this data to your template as ai_insights.")
        
    except Exception as e:
        print(f"\n❌ Error during analysis: {str(e)}")
