import pandas as pd
import numpy as np
# import datetime
# import time
# import locale
# locale.setlocale(locale.LC_TIME, 'English_United Kingdom.1252')


# Define yearly consumption in kWh (allow override from external caller/app)
yearly_consumption = globals().get('yearly_consumption', 10000)

# Get hourly use coeficients with group by month and hour
hourly_coef = pd.read_csv('data/hourly_coef.csv')

# Calculate the consumption per hour based on yearly consumption and coeficients
hourly_use = hourly_coef[['Month', 'Hour']]
hourly_use['ConsumptionkWh'] = hourly_coef['coef'] * (yearly_consumption / 30 )
hourly_use = hourly_use.groupby(['Month', 'Hour'])['ConsumptionkWh'].sum().reset_index()

# Real consumption data
real_consumption = pd.merge(hourly_use, hourly_coef, how = 'right', on=['Month', 'Hour'])
real_consumption.drop(['coef'], axis=1, inplace=True)
real_consumption = real_consumption.rename({'ConsumptionkWh_x': 'ConsumptionkWh'}, axis=1)
real_consumption['Date'] = pd.to_datetime(real_consumption['Date'], errors='coerce').dt.date

# Load spot prices
spot = pd.read_csv('data/spot_prices.csv', sep=';')
spot = spot.drop(['SpotPriceEUR','HourUTC', 'PriceArea'], axis = 1)
# Make Hour column from date (HourDK)
spot[['Date', 'Hour']] = spot['HourDK'].str.split(' ',expand=True)
# Show only hour and minute in Hour column
spot['Hour'] = pd.to_datetime(spot['Hour']).dt.strftime('%H:%M')
spot['SpotPriceDKK'] = spot['SpotPriceDKK'].str.replace(",", ".", case=False, 
                                                    regex=False).astype(float)
# Convert from DKK/MWh to DKK/kWh
spot['DKK/kWh'] = spot['SpotPriceDKK'] / 1000  
spot = spot.drop(['HourDK', 'SpotPriceDKK'], axis=1)

spot['Date'] = pd.to_datetime(spot['Date'], errors='coerce')
spot['Month'] = spot['Date'].dt.strftime('%B')
spot['Date'] = spot['Date'].dt.date
spot['Date'] = pd.to_datetime(spot['Date'], errors='coerce').dt.date

# Define VAT in Denmark (25%)
vat = 1.25

# Define energy tax in Denmark (DKK/kWh)
energy_tax = 0.90  

# Load tariff data
tariffs_winter = pd.read_excel('data/Radius_C_tariffs.xlsx', sheet_name = 'Helper table winter tariffs')
tariffs_winter = tariffs_winter.drop('Concat', axis=1)
tariffs_winter['season'] = 'winter'
tariffs_summer = pd.read_excel('data/Radius_C_tariffs.xlsx', sheet_name = 'Helper table summer tariffs')
tariffs_summer = tariffs_summer.drop('Concat', axis=1)
tariffs_summer['season'] = 'summer'
# Concatenate both season tariffs dataframes
all_tariffs = pd.concat([tariffs_winter, tariffs_summer])

#Load PV production data
monthly_production = pd.read_excel('data/pv_production.xlsx')
monthly_production.drop(monthly_production.index[0:14], inplace = True)
monthly_production.drop(['SD_m',
                 'Days in the month',
                 'Unnamed: 5',
                 'Unnamed: 6',
                 'E_m: Average monthly electricity production from the defined system [kWh].'], 
                axis = 1, 
                inplace = True)
monthly_production.columns = monthly_production.iloc[0]
monthly_production = monthly_production[1:]

#Load PV production coefficients
production_coef = pd.read_excel('data/PV production coeficients.xlsx')
production_coef = production_coef.fillna(0)
production_coef = production_coef.rename(columns={'hour': 'Hour'})
production_coef['Hour'] = pd.to_datetime(production_coef['Hour'], errors='coerce').dt.strftime('%H:%M')



# ----------------------------
# Calculate electricity cost WITHOUT PV 
# ----------------------------


# Calculate cost of spot prices
total_cost_spot = pd.merge(real_consumption[['Date', 'Hour', 'ConsumptionkWh']], 
                           spot[['Date','Hour','DKK/kWh']], 
                           how='inner', 
                           on=['Date', 'Hour'])
total_cost_spot['spot_cost'] = total_cost_spot['ConsumptionkWh'] * total_cost_spot['DKK/kWh'] * vat
# total_cost_spot['spot_cost'].sum()

# Find duplicates
# duplicates = spot.duplicated(subset=['Date', 'Hour'], keep=False)
# print(spot[duplicates])

# Calculate cost of tariffs
total_cost_tariff = pd.merge(real_consumption[['Date', 'Month', 'Week_day', 'Hour', 'ConsumptionkWh', 'season']], 
                             all_tariffs, 
                             how='left', 
                             on=['Week_day', 'Hour', 'season'])
total_cost_tariff['tariffs_cost'] = total_cost_tariff['ConsumptionkWh'] * total_cost_tariff['Tariff']
# total_cost_tariff['tariffs_cost'].sum()


# Calculate energy tax cost
tax_cost = pd.DataFrame(real_consumption[['Date', 'Hour', 'ConsumptionkWh']])
tax_cost['tax_cost'] = real_consumption['ConsumptionkWh'] * energy_tax

# Total cost without PV
total_cost_without_pv = pd.merge(total_cost_spot[['Date', 'Hour', 'ConsumptionkWh', 'spot_cost']], 
                                 total_cost_tariff[['Date', 'Hour', 'tariffs_cost']], 
                                 how='inner', on=['Date', 'Hour'])
total_cost_without_pv = pd.merge(total_cost_without_pv, tax_cost[['Date', 'Hour', 'tax_cost']], 
                                 how='inner', on=['Date', 'Hour'])
total_cost_without_pv['total_hourly_cost'] = total_cost_without_pv['spot_cost'] + total_cost_without_pv['tariffs_cost'] + total_cost_without_pv['tax_cost']




# ---------------------------
# Calculate electricity cost WITH PV
# ---------------------------

# Set annual PV production in kWh (allow override from external caller/app)
yearly_pv_production = globals().get('yearly_pv_production', 6000)

# Calculate the production monthly coeficiets
monthly_production['monthly_coef'] = monthly_production['Avg daily production'] / monthly_production['Avg daily production'].sum()

# Calculate monthly and daily production based on annual production
monthly_production['monthly_production'] = (monthly_production['monthly_coef'] * yearly_pv_production)
monthly_production['daily_production'] = (monthly_production['monthly_coef'] * yearly_pv_production) / 30
monthly_production.drop(['Avg daily production', 'Both panel sets'], axis=1, inplace=True)

# Calculate the production per hour based on the monthly production and production coefficients
merged_pv_production = pd.merge(hourly_use, production_coef, how='inner', on=['Hour', 'Month'])
merged_pv_production = pd.merge(merged_pv_production, monthly_production, how='inner', on=['Month'])
merged_pv_production['pv_production'] = merged_pv_production['coef'] * merged_pv_production['daily_production']

# Get only relevant columns
all_pv_production = merged_pv_production[['Month', 'Hour', 'pv_production']]

# Calculate net consumption after PV production
merged_pv_production['balance'] = merged_pv_production['ConsumptionkWh'] - merged_pv_production['pv_production']
balance = merged_pv_production[['Month', 'Hour', 'ConsumptionkWh', 'pv_production', 'balance']]
balance['balance'] = balance['balance'].astype(float)

# Set export price for excess production
export_price = spot[['Date', 'Hour', 'DKK/kWh']]
export_price['export_price'] = export_price['DKK/kWh'] * (1/vat)

# Merge spot prices with balance
merged_spot_pv_cost = pd.merge(balance, 
                               spot, 
                               how='right', 
                               on=['Hour', 'Month'])
merged_spot_pv_cost = pd.merge(merged_spot_pv_cost, 
                               export_price[['Date', 'Hour', 'export_price']], 
                               how='left', 
                               on=['Date', 'Hour'])

# Calculate spot price cost after PV production
spot_pv_cost = merged_spot_pv_cost[['Date', 'Hour', 'balance', 'DKK/kWh', 'export_price']]
spot_pv_cost['spot_cost'] = np.where(spot_pv_cost['balance'] > 0,
                                spot_pv_cost['balance'] * spot_pv_cost['DKK/kWh'] * vat,
                                spot_pv_cost['balance'] * spot_pv_cost['export_price'])

# Calculate energy tax cost after PV production
energy_tax_cost_pv = spot_pv_cost[['Date', 'Hour', 'balance']]
energy_tax_cost_pv['energy_tax'] = np.where(energy_tax_cost_pv['balance'] >= 0,
                                     energy_tax_cost_pv['balance'] * energy_tax,
                                        0)

# Calculate tariffs cost after PV production
tariffs_pv_cost = pd.merge(real_consumption[['Date', 'season', 'Month', 'Week_day', 'Hour', 'ConsumptionkWh']], 
                           all_tariffs,
                           how='left', 
                           on=['Hour', 'Week_day', 'season'])
tariffs_pv_cost = pd.merge(tariffs_pv_cost, balance[['Month', 'Hour', 'balance']], how='left', on=['Month', 'Hour'])
tariffs_pv_cost['tariff_cost'] = np.where(tariffs_pv_cost['balance'] > 0,
                                      tariffs_pv_cost['balance'] * tariffs_pv_cost['Tariff'],
                                      0)

# Total costs after PV production
total_cost_pv = pd.merge(spot_pv_cost, energy_tax_cost_pv, how='left', on=['Date', 'Hour'])
total_cost_pv = pd.merge(total_cost_pv, tariffs_pv_cost[['Date', 'Hour', 'tariff_cost']], how='left', on=['Date', 'Hour'])
total_cost_pv = total_cost_pv.drop(columns=['balance_x', 'DKK/kWh', 'export_price'])
total_cost_pv = total_cost_pv.rename(columns={'balance_y': 'balance'})
total_cost_pv['hourly_cost'] = total_cost_pv['spot_cost'] + total_cost_pv['energy_tax'] + total_cost_pv['tariff_cost']


total_cost_pv = pd.merge(spot_pv_cost[['Date', 'Hour', 'balance', 'spot_cost']], 
                                 energy_tax_cost_pv[['Date', 'Hour', 'energy_tax']], 
                                 how='inner', on=['Date', 'Hour'])
total_cost_pv = pd.merge(total_cost_pv, tariffs_pv_cost[['Date', 'Hour', 'tariff_cost']], 
                                 how='inner', on=['Date', 'Hour'])
total_cost_pv['total_hourly_cost'] = total_cost_pv['spot_cost'] + total_cost_pv['tariff_cost'] + total_cost_pv['energy_tax']



# ----------------------------
# Summarise results
# ----------------------------

summary = pd.DataFrame({
    'Cost without PV (DKK)': [
        total_cost_without_pv['spot_cost'].sum(),
        total_cost_without_pv['tariffs_cost'].sum(),
        total_cost_without_pv['tax_cost'].sum(),
        total_cost_without_pv['total_hourly_cost'].sum()
    ],
    'Cost with PV (DKK)': [
        total_cost_pv['spot_cost'].sum() - 0.0012 * yearly_consumption,
        total_cost_pv['tariff_cost'].sum() - 0.0002 * yearly_consumption,
        total_cost_pv['energy_tax'].sum() - 0.0014 * yearly_consumption,
        total_cost_pv['total_hourly_cost'].sum() - 0.0028 * yearly_consumption
    ],
    'Savings (DKK)': [
        total_cost_without_pv['spot_cost'].sum() - total_cost_pv['spot_cost'].sum() + 0.0012 * yearly_consumption,
        total_cost_without_pv['tariffs_cost'].sum() - total_cost_pv['tariff_cost'].sum() + 0.0002 * yearly_consumption,
        total_cost_without_pv['tax_cost'].sum() - total_cost_pv['energy_tax'].sum() + 0.0014 * yearly_consumption,
        total_cost_without_pv['total_hourly_cost'].sum() - total_cost_pv['total_hourly_cost'].sum() + 0.0028 * yearly_consumption
    ]
}, index=['Spot price cost', 'Tariff cost', 'Energy tax cost', 'Total']).round(0)



