import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
import pdfplumber
import re

st.title("Expense Tracker App")

uploaded_file = st.file_uploader("Upload your financial statement", type=["pdf"])

def pdf_operations(uploaded_file):
    text = ""
    with pdfplumber.open(uploaded_file) as file:
     for page in file.pages:
        text+=page.extract_text()
    pattern = re.compile(
    r"(?P<date>\w{3} \d{1,2}, \d{4}) (Paid to|Received from|Payment to) (?P<retailer>[\w\s\-\&]+) (?P<type>DEBIT|CREDIT) ₹(?P<amount>\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\n"
    r"(?P<time>\d{1,2}:\d{2} (?:am|pm))"
    )
    transactions = []
    for match in pattern.finditer(text):
     transactions.append(match.groupdict())

    transactions_df = pd.DataFrame(transactions)
    return transactions_df

def preprocessing(transactions_df):
    transactions_df['amount'] = transactions_df['amount'].str.replace(',','')
    transactions_df['amount'] = pd.to_numeric(transactions_df['amount'])
    debits = transactions_df[transactions_df['type']=='DEBIT']
    credits = transactions_df[transactions_df['type']!='DEBIT']
    grouped_by_retailer_debits = debits.groupby('retailer').agg(
        total_amount_spent = ('amount','sum'),
        Highest_amount_spent = ('amount','max'),
        Number_of_transactions_debits = ('amount','count')
    )
    grouped_by_retailer_debits.sort_values(by='total_amount_spent',ascending=False,inplace=True)
    pd.DataFrame(grouped_by_retailer_debits.reset_index(inplace=True))
    major_debitors = grouped_by_retailer_debits['retailer'].unique()
    grouped_by_retailer_credits = credits.groupby('retailer').agg(
        total_amount_credited = ('amount','sum'),
        Number_of_transactions_credits = ('amount','count'),
        Highest_amount_credited = ('amount','max')
    )
    grouped_by_retailer_credits.sort_values(by='total_amount_credited',ascending=False,inplace=True)
    grouped_by_retailer_credits.reset_index(inplace=True)
    major_crediters = grouped_by_retailer_credits['retailer'].unique()
    return debits,credits,grouped_by_retailer_debits,grouped_by_retailer_credits,major_debitors,major_crediters

def datewise_expediture(debits,credits):
    grouped_by_dates_debits = debits.groupby('date').agg(
    spent_in_day = ('amount','sum'),
    no_of_transactions = ('amount','count')
    ).reset_index()
    grouped_by_dates_credits = credits.groupby('date').agg(
    earned_in_day = ('amount','sum'),
    no_of_transactions = ('amount','count')
    ).reset_index()
    merged_df = pd.merge(grouped_by_dates_credits,grouped_by_dates_debits,on='date',how='outer').fillna(0)
    merged_df['Net_credited'] = merged_df['earned_in_day']-merged_df['spent_in_day']
    melted_df = merged_df.melt(id_vars='date',value_vars=['earned_in_day','spent_in_day'])
    fig = px.bar(
        melted_df,
        x = 'date',
        y = 'value',
        color='variable', 
        title="Day-wise Transactions: Debits (Red) Overlayed on Credits (Blue)",
        labels={"date": "Date", "value": "Amount", "variable": "Transaction Type"},
        hover_data={"date": True, "value": True},
        barmode="overlay",
        color_discrete_map={
            'earned_in_day': 'green',  
            'spent_in_day': 'red'      
        }
    )
    fig.add_scatter(
        x = merged_df['date'],
        y = merged_df['Net_credited'],
        mode='lines+markers', 
        name='Net Amount', 
        line=dict(color='black', width=2),
        marker=dict(color='black', size=8)
    )
    st.plotly_chart(fig)

def daywise_expenditure(debits):
    grouped_by_dates_debits = debits.groupby('date').agg(
    spent_in_day = ('amount','sum'),
    no_of_transactions = ('amount','count')
    ).reset_index()
    grouped_by_dates_debits['day'] = grouped_by_dates_debits['date'].dt.day_name()
    weekly_expenditure = grouped_by_dates_debits.groupby(['day', 'date']).agg(
        total_spent=('spent_in_day', 'sum')
    ).reset_index()
    # display(weekly_expenditure)
    pivot_df = weekly_expenditure.pivot(index='date', columns='day', values='total_spent').fillna(0)
    # display(pivot_df)
    melted_df = pivot_df.reset_index().melt(id_vars='date', var_name='day', value_name='amount')
    melted_df['day'] = pd.Categorical(melted_df['day'], categories=[
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
    ], ordered=True)
    fig = px.bar(
        melted_df,
        x="day", 
        y="amount",
        color="date",  
        title="Stacked Weekly Expenditure by Day",
        labels={"day": "Day of the Week", "amount": "Total Expenditure", "date": "Date"},
        hover_data={"date": True, "amount": True},
        barmode="stack"  
    )
    fig.update_layout(
        xaxis_title="Day of the Week",
        yaxis_title="Total Expenditure",
        legend_title="Date"
    )

    st.plotly_chart(fig)

def major_expenditures(grouped_by_retailer_debits):
    st.title("Expenditure Distribution : ")
    fig1 = px.pie(
    names=grouped_by_retailer_debits['retailer'],
    values=grouped_by_retailer_debits['total_amount_spent'],
    )
    st.plotly_chart(fig1)
    st.title("Major Debitors: ")
    st.table(grouped_by_retailer_debits.head(5)) 

def distributuion_of_expenditure(retailer_classification, grouped_by_retailer_debits):
    expenditure_classifications = {}
    retailer_expenditure_map = {}

    for i in range(len(grouped_by_retailer_debits)):
        retailer_expenditure_map[grouped_by_retailer_debits['retailer'].iloc[i]] = grouped_by_retailer_debits['total_amount_spent'].iloc[i]

    for retailer, category in retailer_classification.items():
        if category not in expenditure_classifications:
            expenditure_classifications[category] = 0  
        expenditure_classifications[category] += retailer_expenditure_map.get(retailer, 0)

    return expenditure_classifications
      
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

if uploaded_file is not None:
    transactions_df = pdf_operations(uploaded_file)
    num_days = st.number_input("Enter the number of days for analysis from today",min_value=7)
    transactions_df['date'] = pd.to_datetime(transactions_df['date'], errors='coerce')
    current_date = pd.Timestamp.today()
    start_date = current_date - pd.Timedelta(days=num_days)
    transactions_df = transactions_df[transactions_df['date'] >= start_date]
    debits,credits,grouped_by_retailer_debits,grouped_by_retailer_credits,major_debitors,major_crediters = preprocessing(transactions_df)
    if st.button("Generate Date-Wise Insights"):
       datewise_expediture(debits,credits)

    if st.button("See the Days when you are spending more"):
       daywise_expenditure(debits)

    major_expenditures(grouped_by_retailer_debits)

    if len(major_debitors) > 0:
        st.title("Classify Major Debitors")
        retailer_classifications = classify_retailers(major_debitors)
        

        if st.button("Show Classifications"):
            st.write("Retailer Classifications:")
            for retailer, category in retailer_classifications.items():
                st.write(f"{retailer}: {category}") 
        if st.button("Show Classification of Expenditure"):
            expenditure_classifications =  distributuion_of_expenditure(retailer_classifications,grouped_by_retailer_debits)
            variables = []
            values = []
            for i,j in expenditure_classifications.items():
                 st.write(f"{i}: {j}")
                 variables.append(i)
                 values.append(j)     
            fig = px.pie(
                names=variables,
                values=values 
            )
            st.plotly_chart(fig)     





