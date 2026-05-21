import axios from 'axios';

const deployedApi = 'https://matchfit-pro-backend-production.up.railway.app/api';
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || (import.meta.env.PROD ? deployedApi : 'http://localhost:8080/api'),
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('matchfit-token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use((response) => response, (error) => {
  if (error.response?.status === 401 && !location.pathname.match(/login|register/)) {
    localStorage.removeItem('matchfit-token');
    location.assign('/login');
  }
  return Promise.reject(error);
});

export const errorMessage = (error: any) =>
  error?.response?.data?.error || error?.response?.data?.message || 'That request did not finish.';

export default api;
