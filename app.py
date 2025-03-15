import streamlit as st
import pandas as pd
import plotly.express as px
import pdfplumber
import re

st.title("Expense Tracker App")

uploaded_file = st.file_uploader("Upload your financial statement", type=["pdf"])

def pdf_operations(uploaded_file):
    text = ""
    with pdfplumber.open(uploaded_file) as file:
        for page in file.pages:
            text += page.extract_text()
    pattern = re.compile(
        r"(?P<date>\w{3} \d{1,2}, \d{4}) (Paid to|Received from|Payment to) (?P<retailer>[\w\s\-\&]+) (?P<type>DEBIT|CREDIT) ₹(?P<amount>\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\n"
        r"(?P<time>\d{1,2}:\d{2} (?:am|pm))"
    )
    transactions = [match.groupdict() for match in pattern.finditer(text)]
    return pd.DataFrame(transactions)

def preprocessing(transactions_df):
    transactions_df['amount'] = transactions_df['amount'].astype(str).str.replace(',', '')
    transactions_df['amount'] = pd.to_numeric(transactions_df['amount'])
    debits = transactions_df[transactions_df['type'] == 'DEBIT']
    credits = transactions_df[transactions_df['type'] != 'DEBIT']
    grouped_debits = debits.groupby('retailer').agg(
        total_amount_spent=('amount', 'sum'),
        highest_amount_spent=('amount', 'max'),
        num_transactions=('amount', 'count')
    ).sort_values(by='total_amount_spent', ascending=False)
    grouped_credits = credits.groupby('retailer').agg(
        total_amount_credited=('amount', 'sum'),
        num_transactions=('amount', 'count'),
        highest_amount_credited=('amount', 'max')
    ).sort_values(by='total_amount_credited', ascending=False)
    return debits, credits, grouped_debits, grouped_credits

def datewise_expenditure(debits, credits):
    grouped_debits = debits.groupby('date').agg(spent=('amount', 'sum')).reset_index()
    grouped_credits = credits.groupby('date').agg(earned=('amount', 'sum')).reset_index()
    merged = pd.merge(grouped_credits, grouped_debits, on='date', how='outer').fillna(0)
    merged['net_credited'] = merged['earned']-merged['spent']
    melted = merged.melt(id_vars='date', value_vars=['earned', 'spent'])
    fig = px.bar(
        melted, x='date', y='value', color='variable', barmode='overlay',
        title="Day-wise Transactions: Debits (Red) Overlayed on Credits (Blue)",
        color_discrete_map={'earned': 'green', 'spent': 'red'}
    )
    st.write("The Expenditure in the selected No. of Days is : ")
    st.write(abs(merged['net_credited'].sum()))
    return fig

def weekly_expenditure(debits):
    debits['date'] = pd.to_datetime(debits['date'])
    debits['day'] = debits['date'].dt.day_name()
    weekly = debits.groupby(['day', 'date']).agg(total_spent=('amount', 'sum')).reset_index()
    pivot = weekly.pivot(index='date', columns='day', values='total_spent').fillna(0)
    melted = pivot.reset_index().melt(id_vars='date', var_name='day', value_name='amount')
    fig = px.bar(melted, x='day', y='amount', color='date', barmode='stack',
                 title="Stacked Weekly Expenditure by Day")
    return fig

def expenditure_pie_chart(grouped_debits):
    fig = px.pie(grouped_debits, names=grouped_debits.index, values='total_amount_spent')
    return fig

def classify_retailers(major_debitors):
    retailer_classifications = {}
    for retailer in major_debitors:
        classification = st.selectbox(
            f"Classify retailer {retailer}:",
            ["Food", "Lifestyle", "Electronics", "Fashion", "Other"],
            key=retailer
        )
        retailer_classifications[retailer] = classification
    return retailer_classifications

def classification_pie_chart(classifications, grouped_debits):
    classification_sums = {cat: 0 for cat in set(classifications.values())}
    for retailer, category in classifications.items():
        if retailer in grouped_debits.index:
            classification_sums[category] += grouped_debits.loc[retailer, 'total_amount_spent']
    fig = px.pie(names=classification_sums.keys(), values=classification_sums.values(),
                 title="Classification of Expenditure")
    return fig

if uploaded_file is not None:
    transactions_df = pdf_operations(uploaded_file)
    transactions_df['date'] = pd.to_datetime(transactions_df['date'], errors='coerce')
    debits, credits, grouped_debits, grouped_credits = preprocessing(transactions_df)

    page = st.sidebar.radio("Navigation", ["Home","Date-Wise Analysis", "Weekly Expenditure", "Major Expenditures", "Classify Retailers"])

    if page == "Date-Wise Analysis":
        num_days = st.number_input("Enter the number of days for analysis", min_value=7)
        start_date = pd.Timestamp.today() - pd.Timedelta(days=num_days)
        filtered_df = transactions_df[transactions_df['date'] >= start_date]
        debits, credits, _, _ = preprocessing(filtered_df)
        st.plotly_chart(datewise_expenditure(debits, credits))

    elif page == "Weekly Expenditure":
        st.plotly_chart(weekly_expenditure(debits))

    elif page == "Major Expenditures":
        st.plotly_chart(expenditure_pie_chart(grouped_debits))
        st.table(grouped_debits.head(5))

    elif page == "Classify Retailers":
        retailer_classifications = classify_retailers(grouped_debits.index)
        st.write("Retailer Classifications:")
        for retailer, category in retailer_classifications.items():
            st.write(f"{retailer}: {category}")
        if st.button("Show Classification of Expenditure"):
            st.plotly_chart(classification_pie_chart(retailer_classifications, grouped_debits))
