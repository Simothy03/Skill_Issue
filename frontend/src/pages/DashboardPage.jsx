import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from './Sidebar'
import { useRef } from "react";

const API_URL = import.meta.env.REACT_APP_API_URL || import.meta.env.VITE_REACT_APP_API_URL;

const API = API_URL ? `${API_URL}` : "http://localhost:5000"; 

// Helper function to format month and year (e.g., "2023-01")
const getMonthYearString = (date) => {
    const year = date.getFullYear();
    // Months are 0-indexed, so we add 1 and pad with '0'
    const month = String(date.getMonth() + 1).padStart(2, '0');
    return `${year}-${month}`;
};

// Helper function to get the current and previous 12 month-year strings
const getMonthYearOptions = (count = 24) => {
    const options = [];
    let date = new Date(); // Start with the current date (for the latest month)
    
    // Set the date to the first day of the current month to ensure consistency
    date.setDate(1); 
    
    for (let i = 0; i < count; i++) {
        options.push(getMonthYearString(date));
        // Move back one month
        date.setMonth(date.getMonth() - 1);
    }
    return options.reverse(); // Reverse to show oldest first
};

const monthYearOptions = getMonthYearOptions();

const HabitsDisplay = ({ analysisResults }) => {
    // Check for required data structure
    if (!analysisResults || !analysisResults.habits || analysisResults.habits.length === 0) {
        return (
            <div className="mt-6 p-4 bg-yellow-50 text-yellow-800 border-l-4 border-yellow-400 rounded-md">
                <p className="font-medium">No distinct habits found in the selected time range.</p>
                <p className="text-sm mt-1">Try analyzing more games or a longer date range.</p>
            </div>
        );
    }

    return (
      <div className="mt-6 space-y-8">
          <h2 className="text-3xl font-bold text-gray-900 border-b pb-2">Your Chess Habits</h2>
          
          {analysisResults.habits.map((habit, index) => (
              <div key={index} className="p-6 bg-white border border-indigo-200 rounded-xl shadow-lg">
                  <div className="flex items-center justify-between mb-3">
                      <h3 className="text-xl font-extrabold text-indigo-700">
                          {index + 1}. {habit.habit_name.replace(` (H${habit.hdbscan_cluster_id})`, '')}
                      </h3>
                      <span className="text-sm font-semibold text-gray-500 bg-indigo-50 px-3 py-1 rounded-full">
                          {/* Use a placeholder since confidence is NULL */}
                          Confidence: {habit.confidence ? Math.round(habit.confidence * 100) : 'N/A'}
                      </span>
                  </div>

                  {/* Coaching Insight (Mapping to the combined feedback_text) */}
                  <div className="mt-4 p-4 bg-indigo-50 border-l-4 border-indigo-400 rounded-md">
                      <p className="font-semibold text-indigo-800">Coaching Insight:</p>
                      {/* CHANGE: Use the feedback_text field, which is aliased from f.description */}
                      <p className="text-gray-700 mt-1">{habit.feedback_text || habit.habit_description || 'No detailed coaching insight found.'}</p>
                  </div>

                  {/* Improvement Tip (Mapping to the combined feedback_text as well, or a placeholder) */}
                  <div className="mt-4 p-4 bg-green-50 border-l-4 border-green-400 rounded-md">
                      <p className="font-semibold text-green-800">Improvement Tip:</p>
                      {/* CHANGE: Use the same field, since the Tip field is not dedicated */}
                      <p className="text-gray-700 mt-1">
                          {habit.improvement_tip || (habit.feedback_text ? habit.feedback_text.split('.')[0] + '.' : 'No specific tip provided. See insight above.')}
                      </p>
                  </div>
                  
                  {/* Key Details (Optional, for debugging or advanced users) */}
                  <details className="mt-4 text-sm text-gray-600 cursor-pointer">
                      <summary className="font-medium text-gray-700 hover:text-indigo-600">
                          Advanced Details ({habit.total_mistakes} Mistakes)
                      </summary>
                      <ul className="mt-2 list-disc list-inside space-y-1 bg-gray-50 p-3 rounded-md">
                          <li>Number of Mistakes Clustered: {habit.total_mistakes}</li>
                          {/* Fallback for missing fields */}
                          <li>"Prime" Example of a Mistake (ID): {habit.prime_example_mistake_id || 'N/A'}</li> 
                          <li>Cluster ID (HDBScan): {habit.hdbscan_cluster_id ?? 'N/A'}</li> 
                      </ul>
                  </details>
              </div>
          ))}
      </div>
  );
};

export default function DashboardPage() {
  const [userInfo, setUserInfo] = useState(null);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  // State for the "Link Account" form
  const [linkUsername, setLinkUsername] = useState('');
  const [linkMessage, setLinkMessage] = useState('');

  // State for the date range
  const [startMonthYear, setStartMonthYear] = useState(monthYearOptions[monthYearOptions.length - 6] || ''); // Default to 6 months ago
  const [endMonthYear, setEndMonthYear] = useState(monthYearOptions[monthYearOptions.length - 1] || '');   // Default to the most recent month

  // State for analysis
  const [analysisResults, setAnalysisResults] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  
  const navigate = useNavigate();

  const hasFetched = useRef(false);

  // Function to fetch user status (we'll call this on load and after linking)
  const fetchUserStatus = async () => {
  try {
    const response = await fetch(`${API}/api/user/status`, {
      method: 'GET',
      credentials: 'include',
    });

    const data = await response.json();

    if (data.logged_in) {
      setIsLoggedIn(true);
      setUserInfo(data.user_info);
    } else {
      navigate('/login?error=session_expired');
    }

  } catch (err) {
    setError('Failed to fetch user status.');
  } finally {
    setLoading(false);
    hasFetched.current = true;
  }
};

  const fetchSavedHabits = async () => {
    try {
        const response = await fetch(`${API}/api/user/latest-habits`, {
            method: 'GET',
            credentials: 'include',
        });
        const data = await response.json();
        if (response.ok && data.habits && data.habits.length > 0) {
            // This populates the UI with the previous analysis automatically
            setAnalysisResults({ habits: data.habits });
        }
    } catch (err) {
        console.error("Could not restore session habits", err);
    }
  };

  // Fetch user status on component load
  useEffect(() => {
    const init = async () => {
        await fetchUserStatus(); // Get user info first
    };
    init();
}, [navigate]);

  useEffect(() => {
    if (isLoggedIn && userInfo?.chess_com_username) {
        fetchSavedHabits();
    }
}, [isLoggedIn, userInfo]);

  // Handler for the "Link Account" form
  const handleLinkAccount = async (e) => {
    e.preventDefault();
    setLinkMessage(''); // Clear previous messages
    if (!linkUsername) {
      setLinkMessage('Please enter a username.');
      return;
    }

    try {
      const response = await fetch(`${API}/api/user/link_chess_account`, {
        method: 'POST',
        credentials: 'include', // Send cookies
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username: linkUsername }),
      });
      
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to link account');
      }

      setLinkMessage(data.message || 'Account linked!');
      // Refresh user info to show the new "Analyze" button
      await fetchUserStatus(); 
      setLinkUsername(''); // Clear input
      
    } catch (err) {
      setLinkMessage(err.message);
    }
  };

  // Handler for the "Analyze" button
  const handleAnalyze = async () => {
    // Date validation
    if (startMonthYear > endMonthYear) {
        setError('Start date cannot be after the end date.');
        return;
    }

    // setAnalysisResults(null);
    setAnalysisLoading(true);
    setError('');

    try {
      const response = await fetch(`${API}/api/analyze`, {
        method: 'POST',
        credentials: 'include', // Send cookies
        headers: {
            'Content-Type': 'application/json',
        },
        // Send the date range in the request body
        body: JSON.stringify({ 
            start_month_year: startMonthYear, 
            end_month_year: endMonthYear 
        }),
      });
      
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Analysis failed');
      }
      
      setAnalysisResults(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setAnalysisLoading(false);
    }
  };

  // Show loading spinner while checking auth
  if (loading && !hasFetched.current) {
    return <div className="min-h-screen bg-gray-100 flex items-center justify-center"><p>Loading...</p></div>;
  }
  
  // Show this if user is somehow not logged in
  if (!isLoggedIn) {
      // This shouldn't be seen if the useEffect redirect works, but it's good practice
    return <div className="min-h-screen bg-gray-100 flex items-center justify-center"><p>Please <a href="/login" className="text-blue-600">login</a>.</p></div>;
  }

  // Main dashboard content
  return (
    <Sidebar>
    <div className="w-full">
      <div className="max-w-4xl mx-auto bg-white p-6 rounded-lg shadow-md">
        
        <div className="mb-4">
          <h1 className="text-3xl font-bold text-gray-900">
            Welcome, {userInfo?.name || 'User'}!
          </h1>
        </div>

        <hr className="my-6" />

        {/* === CONDITIONAL SECTION === */}
        {/* Check if chess_com_username is linked */}
        {!userInfo?.chess_com_username ? (
          // STATE 1: No username is linked
          <div>
            <h2 className="text-2xl font-semibold mb-4">Link Your Chess.com Account</h2>
            <p className="text-gray-600 mb-4">
              To begin analyzing your games, please link your Chess.com account.
            </p>
            <form onSubmit={handleLinkAccount}>
              <label htmlFor="link-username" className="block text-sm font-medium text-gray-700">
                Chess.com Username
              </label>
              <div className="mt-1 flex rounded-md shadow-sm">
                <input
                  type="text"
                  id="link-username"
                  value={linkUsername}
                  onChange={(e) => setLinkUsername(e.target.value)}
                  className="flex-1 block w-full rounded-none rounded-l-md border-gray-300 focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2"
                  placeholder="e.g., Hikaru"
                />
                <button
                  type="submit"
                  className="inline-flex items-center rounded-r-md border border-l-0 border-gray-300 bg-gray-50 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
                >
                  Link Account
                </button>
              </div>
              {linkMessage && (
                <p className={`mt-2 text-sm ${linkMessage.includes('failed') || linkMessage.includes('Error') || linkMessage.includes('already linked') ? 'text-red-600' : 'text-green-600'}`}>
                  {linkMessage}
                </p>
              )}
            </form>
          </div>
        ) : (
          // STATE 2: Username is linked
          <div>
            <h2 className="text-2xl font-semibold mb-4">Analyze Your Games</h2>
            <p className="text-gray-600 mb-4">
              Your linked Chess.com account: <strong className="text-gray-900">{userInfo.chess_com_username}</strong>
            </p>
            
            <div className="mb-4 p-4 border border-gray-200 rounded-md">
                <h3 className="text-lg font-medium mb-3">Select Game Date Range</h3>
                <div className="flex space-x-4">
                    <div className="flex-1">
                        <label htmlFor="start-month" className="block text-sm font-medium text-gray-700">
                            Start Month/Year
                        </label>
                        <select
                            id="start-month"
                            value={startMonthYear}
                            onChange={(e) => setStartMonthYear(e.target.value)}
                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm py-2"
                        >
                            {monthYearOptions.map(my => (
                                <option key={my} value={my}>{my}</option>
                            ))}
                        </select>
                    </div>
                    <div className="flex-1">
                        <label htmlFor="end-month" className="block text-sm font-medium text-gray-700">
                            End Month/Year
                        </label>
                        <select
                            id="end-month"
                            value={endMonthYear}
                            onChange={(e) => setEndMonthYear(e.target.value)}
                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm py-2"
                        >
                            {monthYearOptions.map(my => (
                                <option key={my} value={my}>{my}</option>
                            ))}
                        </select>
                    </div>
                </div>
            </div>
            
            <p className="text-gray-600 mb-4">
              Click the button below to fetch and analyze your games within the selected range.
            </p>
            <button
              onClick={handleAnalyze}
              disabled={analysisLoading}
              className="px-6 py-2 bg-indigo-600 text-white font-semibold rounded-md shadow-sm hover:bg-indigo-500 disabled:bg-gray-400"
            >
              {analysisLoading ? 'Analyzing...' : 'Analyze Selected Games'}
            </button>
            <p className="text-sm text-gray-500 mt-2">
              Want to analyze a different account? You can change your linked account on the Settings page.
            </p>
          </div>
        )}

        {/* === Analysis Results Section === */}
        {error && (
          <div className="mt-6 p-4 bg-red-100 text-red-700 rounded-md">
            <h3 className="font-bold">Error</h3>
            <p>{error}</p>
          </div>
        )}
        
        {/* Show results if they exist, even if we are currently loading NEW ones */}
        {analysisResults && (
            <div className={analysisLoading ? "opacity-50 pointer-events-none" : ""}>
                {analysisLoading && (
                    <p className="text-indigo-600 font-bold animate-pulse mb-2">
                        Please do not leave this screen. Updating your habits with new games. This may take a few minutes...
                    </p>
                )}
                <HabitsDisplay analysisResults={analysisResults} />
            </div>
        )}

        {/* Keep your existing big loading spinner for when there is NO data at all */}
        {analysisLoading && !analysisResults && (
            <div className="mt-6 flex justify-center items-center p-8 border border-gray-300 rounded-md">
                <p>Please do not leave this screen. Analyzing for the first time. This may take a few minutes...</p>
            </div>
        )}
        
      </div>
    </div>
  </Sidebar>
  );
}