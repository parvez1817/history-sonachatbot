from crewai.tools import BaseTool
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
import requests
import re


COLLECTION = "sona_knowledge"

client = QdrantClient(path="qdrant_local_db")


# ---------------- EMBEDDING ----------------
def embed(text: str):
    r = requests.post(
        "http://localhost:11434/api/embeddings",
        json={"model": "nomic-embed-text", "prompt": text},
        timeout=60
    )
    r.raise_for_status()
    return r.json()["embedding"]


# ---------------- ENHANCED QUERY PARSER ----------------
def parse_query(q: str):
    """
    Extracts: department code, category, and year from query
    Handles both codes (ECE) and full names (Electronics and Communication Engineering)
    """
    q_lower = q.lower()

    # IMPORTANT → longest categories first (prevents BC matching BCM)
    categories = ["bcm", "mbc", "sca", "oc", "bc", "sc", "st"]
    
    # Map full department names to codes
    dept_mapping = {
        # Codes (for backward compatibility)
        "cse": "CSE",
        "ads": "ADS", 
        "it": "IT",
        "aml": "AML",
        "ece": "ECE",
        "eee": "EEE",
        "mech": "MECH",
        "civil": "CIVIL",
        "ft": "FT",
        
        # Full names (flexible matching)
        "computer science": "CSE",
        "computer science and engineering": "CSE",
        "computer science & engineering": "CSE",
        "comp science": "CSE",
        "cs": "CSE",
        
        "artificial intelligence and data science": "ADS",
        "ai and data science": "ADS",
        "data science": "ADS",
        "aids": "ADS",
        
        "information technology": "IT",
        "info tech": "IT",
        
        "ai & machine learning": "AML",
        "ai and machine learning": "AML",
        "artificial intelligence and machine learning": "AML",
        "machine learning": "AML",
        "aiml": "AML",
        
        "electronics and communication": "ECE",
        "electronics and communication engineering": "ECE",
        "electronics & communication": "ECE",
        "ece": "ECE",
        
        "electrical and electronics": "EEE",
        "electrical and electronics engineering": "EEE",
        "electrical & electronics": "EEE",
        
        "mechanical": "MECH",
        "mechanical engineering": "MECH",
        
        "civil engineering": "CIVIL",
        
        "fashion technology": "FT",
        "fashion tech": "FT",
    }

    dept = None
    cat = None
    year = None

    # Extract department - try longest matches first
    sorted_depts = sorted(dept_mapping.keys(), key=len, reverse=True)
    for dept_pattern in sorted_depts:
        if dept_pattern in q_lower:
            dept = dept_mapping[dept_pattern]
            break

    # Extract category (strict whole word match)
    for c in categories:
        if re.search(rf"\b{c}\b", q_lower):
            cat = c.upper()
            break

    # Extract year (match 4-digit year or 2-digit year)
    year_match = re.search(r"\b(20\d{2}|\d{2})\b", q_lower)
    if year_match:
        year_str = year_match.group(1)
        # Convert 2-digit to 4-digit (23 -> 2023, 24 -> 2024, 25 -> 2025)
        if len(year_str) == 2:
            year = 2000 + int(year_str)
        else:
            year = int(year_str)

    return dept, cat, year


# ---------------- HYBRID SEARCH WITH YEAR FILTER ----------------
def search_cutoffs(query: str, verbose: bool = False):
    """
    Search for cutoff information with support for department, category, and year filtering
    
    Args:
        query: Natural language query about cutoffs
        verbose: If True, prints debug information about parsed query
        
    Returns:
        Formatted cutoff information string
    """
    dept, cat, year = parse_query(query)

    # Debug output for agent to see what was parsed
    if verbose:
        parsed_info = f"📋 Extracted → Department: {dept or 'Any'}, Category: {cat or 'Any'}, Year: {year or 'Any'}"
        print(parsed_info)

    # =========================================================
    # 1️⃣ STRICT FILTER SEARCH (FAST + EXACT)
    # =========================================================
    conditions = []

    if dept:
        conditions.append(
            FieldCondition(key="code", match=MatchValue(value=dept))
        )

    if cat:
        conditions.append(
            FieldCondition(key="category", match=MatchValue(value=cat))
        )

    if year:
        conditions.append(
            FieldCondition(key="year", match=MatchValue(value=year))
        )

    if conditions:
        results = client.query_points(
            collection_name=COLLECTION,
            query=embed(query),
            query_filter=Filter(must=conditions),
            limit=5
        ).points

        if results:
            # Prepend parsed info for agent context
            result_text = "\n".join(format_result(r.payload) for r in results)
            if verbose:
                return f"{parsed_info}\n\n{result_text}"
            return result_text
        else:
            # If no exact match with all filters, try without year
            if year and len(conditions) > 1:
                conditions_no_year = [c for c in conditions if c.key != "year"]
                
                results = client.query_points(
                    collection_name=COLLECTION,
                    query=embed(query),
                    query_filter=Filter(must=conditions_no_year),
                    limit=5
                ).points
                
                if results:
                    result_text = "\n".join(format_result(r.payload) for r in results)
                    fallback_msg = f"⚠️ No data for year {year}, showing available years:"
                    if verbose:
                        return f"{parsed_info}\n{fallback_msg}\n\n{result_text}"
                    return f"{fallback_msg}\n\n{result_text}"

    # =========================================================
    # 2️⃣ VECTOR FALLBACK (if parsing failed)
    # =========================================================
    results = client.query_points(
        collection_name=COLLECTION,
        query=embed(query),
        limit=5
    ).points

    result_text = "\n".join(format_result(r.payload) for r in results)
    
    # Let agent know parsing might have failed
    if not (dept or cat or year):
        hint = "ℹ️ Could not extract specific filters, showing semantic matches:"
        if verbose:
            return f"{parsed_info}\n{hint}\n\n{result_text}"
        return f"{hint}\n\n{result_text}"
    
    if verbose:
        return f"{parsed_info}\n\n{result_text}"
    return result_text


# ---------------- CLEAN OUTPUT WITH YEAR ----------------
def format_result(p):
    """
    Format search result with year and available seats information
    """
    max_v = p.get("max")
    min_v = p.get("min")
    year = p.get("year", "N/A")
    seats = p.get("available_seats")

    max_v = max_v if max_v is not None else "not available"
    min_v = min_v if min_v is not None else "not available"

    result = (
        f"{p['department']} ({p['code']}) "
        f"[{p['category']}] {year} → "
        f"max {max_v}, min {min_v}"
    )
    
    if seats:
        result += f" | {seats} seats"
    
    return result


# ============================
# ⭐ CREWAI TOOL WRAPPER
# ============================

class CollegeSearchTool(BaseTool):
    name: str = "College Knowledge Search"
    description: str = (
        "Search college cutoff information for Sona College of Technology. "
        "This tool automatically extracts key information from natural language queries:\n"
        "- Department: Recognizes codes (CSE, IT, ECE) and full names (Computer Science and Engineering)\n"
        "- Category: OC, BC, BCM, MBC, SC, SCA, ST\n"
        "- Year: 2023, 2024, 2025\n\n"
        "Examples:\n"
        "- 'CSE OC cutoff for 2024'\n"
        "- 'Computer Science & Engineering MBC in the year 2024'\n"
        "- 'What is the cutoff for Electronics and Communication BC?'\n"
        "- 'Show me IT department cutoffs'\n\n"
        "The tool shows what filters were extracted and returns matching results."
    )

    def _run(self, query: str) -> str:
        """
        Execute the college knowledge search with verbose output
        
        Args:
            query: Natural language query about cutoffs
            
        Returns:
            Formatted cutoff information with extracted parameters
        """
        # Enable verbose mode so agent can see what was extracted
        return search_cutoffs(query, verbose=True)


# Create the tool instance
college_search_tool = CollegeSearchTool()