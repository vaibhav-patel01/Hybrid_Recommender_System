import pandas
import numpy
def search_all_anime_id(name, df):                     # this will give all the matching animes
    name_lower = name.lower().strip()

    # Always run partial match to catch sequels/seasons too
    partial_mask = df['title'].apply(
        lambda titles: any(name_lower in str(t).lower() for t in titles)
        if isinstance(titles, list) else name_lower in str(titles).lower()
    )
    result = df[partial_mask][['id', 'title',"type"]]

    if result.empty:
        return {}

    # Pick display name: second title if exists, else first
    def pick_name(titles):
        if isinstance(titles, list) and len(titles) > 1:
            return str(titles[1])
        elif isinstance(titles, list):
            return str(titles[0])
        return str(titles)

    return {
        # f"{pick_name(row['title'])} [{row['type']}]": int(row['id'])
        # for _, row in result.iterrows()

        # If it's an ANIME, return just the title. Otherwise, return "Title [TYPE]"
        pick_name(row['title']) if row['type'] == "ANIME" else f"{pick_name(row['title'])} [{row['type']}]": int(
            row['id'])
        for _, row in result.iterrows()
    }

def search_anime_id(name, df):                # this will give exact matching
    name_lower = name.lower().strip()

    # Step 1: Try EXACT match first
    exact_mask = df['title'].apply(
        lambda titles: any(str(t).lower() == name_lower for t in titles)
        if isinstance(titles, list) else str(titles).lower() == name_lower
    )
    result = df[exact_mask][['id', 'title']]

    # Step 2: Fall back to partial match
    if result.empty:
        partial_mask = df['title'].apply(
            lambda titles: any(name_lower in str(t).lower() for t in titles)
            if isinstance(titles, list) else name_lower in str(titles).lower()
        )
        result = df[partial_mask][['id', 'title']]

    if result.empty:
        return {}  # nothing found

    # Pick display name: second title if exists, else first
    def pick_name(titles):
        if isinstance(titles, list) and len(titles) > 1:
            return str(titles[1])  # second name
        elif isinstance(titles, list):
            return str(titles[0])  # only one name
        return str(titles)

    # Return dict: { display_name: anime_id }
    return {
        pick_name(row['title']) if row['type'] == "ANIME" else f"{pick_name(row['title'])} [{row['type']}]": int(
            row['id'])
        for _, row in result.iterrows()
    }
