import logging
from typing import List, Dict, Optional
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json

logger = logging.getLogger(__name__)

DARK_THEME = {
    'template': 'plotly_dark',
    'paper_bgcolor': '#1e1e1e',
    'plot_bgcolor': '#1e1e1e',
    'font': {'color': '#e0e0e0', 'size': 12},
    'xaxis': {'gridcolor': '#3e3e3e', 'showgrid': True},
    'yaxis': {'gridcolor': '#3e3e3e', 'showgrid': True}
}

class StockVisualizer:
    
    @staticmethod
    def create_candlestick_chart(df: pd.DataFrame, symbol: str) -> str:
        """
        Create interactive candlestick chart with volume using Plotly
        """
        try:
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.03,
                row_heights=[0.7, 0.3],
                subplot_titles=(f'{symbol} - Candlestick Chart', 'Volume')
            )
            
            fig.add_trace(
                go.Candlestick(
                    x=df.index,
                    open=df['open'],
                    high=df['high'],
                    low=df['low'],
                    close=df['close'],
                    name='Price',
                    increasing_line_color='#26a69a',
                    decreasing_line_color='#ef5350'
                ),
                row=1, col=1
            )
            
            if len(df) >= 20:
                df['SMA20'] = df['close'].rolling(window=20).mean()
                fig.add_trace(
                    go.Scatter(
                        x=df.index,
                        y=df['SMA20'],
                        name='SMA 20',
                        line=dict(color='orange', width=1.5)
                    ),
                    row=1, col=1
                )
            
            if len(df) >= 50:
                df['SMA50'] = df['close'].rolling(window=50).mean()
                fig.add_trace(
                    go.Scatter(
                        x=df.index,
                        y=df['SMA50'],
                        name='SMA 50',
                        line=dict(color='blue', width=1.5)
                    ),
                    row=1, col=1
                )
            
            colors = ['#26a69a' if df['close'].iloc[i] >= df['open'].iloc[i] else '#ef5350' 
                     for i in range(len(df))]
            
            fig.add_trace(
                go.Bar(
                    x=df.index,
                    y=df['volume'],
                    name='Volume',
                    marker_color=colors,
                    opacity=0.6
                ),
                row=2, col=1
            )
            
            fig.update_layout(
                template='plotly_dark',
                paper_bgcolor='#1e1e1e',
                plot_bgcolor='#1e1e1e',
                font=dict(color='#e0e0e0', size=12),
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                xaxis_rangeslider_visible=False,
                height=600,
                margin=dict(l=50, r=50, t=80, b=50)
            )
            
            fig.update_xaxes(
                gridcolor='#3e3e3e',
                showgrid=True,
                row=2, col=1
            )
            
            fig.update_yaxes(
                title_text="Price (x1,000 VND)",
                gridcolor='#3e3e3e',
                showgrid=True,
                row=1, col=1
            )
            
            fig.update_yaxes(
                title_text="Volume",
                gridcolor='#3e3e3e',
                showgrid=True,
                row=2, col=1
            )
            
            return fig.to_json()
            
        except Exception as e:
            logger.error(f"Error creating candlestick chart: {e}")
            return ""
    
    @staticmethod
    def create_technical_analysis_chart(df: pd.DataFrame, symbol: str) -> str:
        """
        Create interactive technical analysis chart with RSI and MACD
        """
        try:
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            
            fig = make_subplots(
                rows=3, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.05,
                row_heights=[0.5, 0.25, 0.25],
                subplot_titles=(
                    f'{symbol} - Technical Analysis',
                    'RSI (14)',
                    'MACD'
                )
            )
            
            df['SMA20'] = df['close'].rolling(window=20).mean()
            df['std20'] = df['close'].rolling(window=20).std()
            df['Upper_BB'] = df['SMA20'] + (df['std20'] * 2)
            df['Lower_BB'] = df['SMA20'] - (df['std20'] * 2)
            
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['close'],
                    name='Close Price',
                    line=dict(color='white', width=1.5)
                ),
                row=1, col=1
            )
            
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['SMA20'],
                    name='SMA 20',
                    line=dict(color='blue', width=1)
                ),
                row=1, col=1
            )
            
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['Upper_BB'],
                    name='Upper BB',
                    line=dict(color='gray', width=1, dash='dash'),
                    showlegend=False
                ),
                row=1, col=1
            )
            
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['Lower_BB'],
                    name='Lower BB',
                    line=dict(color='gray', width=1, dash='dash'),
                    fill='tonexty',
                    fillcolor='rgba(128,128,128,0.2)',
                    showlegend=False
                ),
                row=1, col=1
            )
            
            if len(df) > 14:
                delta = df['close'].diff()
                gain = delta.mask(delta < 0, 0)
                loss = -delta.mask(delta > 0, 0)
                avg_gain = gain.rolling(window=14).mean()
                avg_loss = loss.rolling(window=14).mean()
                rs = avg_gain / avg_loss
                df['RSI'] = 100 - (100 / (1 + rs))
                
                fig.add_trace(
                    go.Scatter(
                        x=df.index,
                        y=df['RSI'],
                        name='RSI',
                        line=dict(color='purple', width=1.5)
                    ),
                    row=2, col=1
                )
                
                fig.add_hline(
                    y=70, line_dash="dash", line_color="red",
                    annotation_text="Overbought", row=2, col=1
                )
                fig.add_hline(
                    y=30, line_dash="dash", line_color="green",
                    annotation_text="Oversold", row=2, col=1
                )
                
                fig.add_hrect(
                    y0=30, y1=70,
                    fillcolor="gray", opacity=0.1,
                    row=2, col=1
                )
            
            if len(df) >= 26:
                exp1 = df['close'].ewm(span=12, adjust=False).mean()
                exp2 = df['close'].ewm(span=26, adjust=False).mean()
                df['MACD'] = exp1 - exp2
                df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
                df['Histogram'] = df['MACD'] - df['Signal']
                
                fig.add_trace(
                    go.Scatter(
                        x=df.index,
                        y=df['MACD'],
                        name='MACD',
                        line=dict(color='blue', width=1.5)
                    ),
                    row=3, col=1
                )
                
                fig.add_trace(
                    go.Scatter(
                        x=df.index,
                        y=df['Signal'],
                        name='Signal',
                        line=dict(color='red', width=1.5)
                    ),
                    row=3, col=1
                )
                
                colors = ['green' if val >= 0 else 'red' for val in df['Histogram']]
                
                fig.add_trace(
                    go.Bar(
                        x=df.index,
                        y=df['Histogram'],
                        name='Histogram',
                        marker_color=colors,
                        opacity=0.3
                    ),
                    row=3, col=1
                )
                
                fig.add_hline(y=0, line_color="white", line_width=0.5, row=3, col=1)
            
            fig.update_layout(
                template='plotly_dark',
                paper_bgcolor='#1e1e1e',
                plot_bgcolor='#1e1e1e',
                font=dict(color='#e0e0e0', size=12),
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                height=800,
                margin=dict(l=50, r=50, t=80, b=50)
            )
            
            fig.update_xaxes(gridcolor='#3e3e3e', showgrid=True)
            fig.update_yaxes(gridcolor='#3e3e3e', showgrid=True)
            
            fig.update_yaxes(title_text="Price", row=1, col=1)
            fig.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1)
            fig.update_yaxes(title_text="MACD", row=3, col=1)
            
            return fig.to_json()
            
        except Exception as e:
            logger.error(f"Error creating technical analysis chart: {e}")
            return ""
    
    @staticmethod
    def create_multi_stock_comparison(stock_data_dict: Dict[str, pd.DataFrame]) -> str:
        """
        Create interactive comparison chart for multiple stocks
        """
        try:
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.05,
                row_heights=[0.7, 0.3],
                subplot_titles=('Price Comparison (Normalized %)', 'Volume Comparison')
            )
            
            colors = ['#00d9ff', '#ff6b6b', '#4ecdc4', '#ffe66d', '#a8dadc']
            
            for idx, (symbol, df) in enumerate(stock_data_dict.items()):
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index)
                
                normalized = (df['close'] / df['close'].iloc[0] - 1) * 100
                
                fig.add_trace(
                    go.Scatter(
                        x=df.index,
                        y=normalized,
                        name=symbol,
                        line=dict(color=colors[idx % len(colors)], width=2)
                    ),
                    row=1, col=1
                )
                
                fig.add_trace(
                    go.Bar(
                        x=df.index,
                        y=df['volume'],
                        name=f'{symbol} Vol',
                        marker_color=colors[idx % len(colors)],
                        opacity=0.6
                    ),
                    row=2, col=1
                )
            
            fig.add_hline(y=0, line_color="white", line_width=0.5, row=1, col=1)
            
            fig.update_layout(
                template='plotly_dark',
                paper_bgcolor='#1e1e1e',
                plot_bgcolor='#1e1e1e',
                font=dict(color='#e0e0e0', size=12),
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                height=700,
                margin=dict(l=50, r=50, t=80, b=50),
                hovermode='x unified'
            )
            
            fig.update_xaxes(gridcolor='#3e3e3e', showgrid=True)
            fig.update_yaxes(gridcolor='#3e3e3e', showgrid=True)
            
            fig.update_yaxes(title_text="% Change", row=1, col=1)
            fig.update_yaxes(title_text="Volume", row=2, col=1)
            
            return fig.to_json()
            
        except Exception as e:
            logger.error(f"Error creating comparison chart: {e}")
            return ""

class GoldVisualizer:
    
    @staticmethod
    def create_gold_price_chart(df: pd.DataFrame, title: str = "Gold Price") -> str:
        """Create interactive gold price trend chart"""
        try:
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            
            fig = go.Figure()
            
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['price'],
                    name='Gold Price',
                    line=dict(color='gold', width=2),
                    fill='tozeroy',
                    fillcolor='rgba(255, 215, 0, 0.1)'
                )
            )
            
            if len(df) >= 7:
                df['MA7'] = df['price'].rolling(window=7).mean()
                fig.add_trace(
                    go.Scatter(
                        x=df.index,
                        y=df['MA7'],
                        name='7-day MA',
                        line=dict(color='orange', width=1.5, dash='dash')
                    )
                )
            
            fig.update_layout(
                title=title,
                template='plotly_dark',
                paper_bgcolor='#1e1e1e',
                plot_bgcolor='#1e1e1e',
                font=dict(color='#e0e0e0', size=12),
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                height=500,
                margin=dict(l=50, r=50, t=80, b=50),
                xaxis=dict(gridcolor='#3e3e3e', showgrid=True),
                yaxis=dict(
                    title='Price (USD/oz)',
                    gridcolor='#3e3e3e',
                    showgrid=True
                )
            )
            
            return fig.to_json()
            
        except Exception as e:
            logger.error(f"Error creating gold chart: {e}")
            return ""
