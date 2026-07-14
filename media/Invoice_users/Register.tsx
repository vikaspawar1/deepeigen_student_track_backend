import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'react-router-dom';
import './auth.css'; // Import the external CSS file

// Define the shape for the form data
interface FormData {
  firstName: string;
  lastName: string;
  email: string;
  username: string;
  profession: string;
  phoneNo: string;
  password: string;
  reEnterPassword: string;
  country: string;
}

const Register: React.FC = () => {
  // State to hold all form data
  const [formData, setFormData] = useState<FormData>({
    firstName: '',
    lastName: '',
    email: '',
    username: '',
    profession: '',
    phoneNo: '',
    password: '',
    reEnterPassword: '',
    country: '',
  });

  // State to toggle password visibility
  const [showPassword, setShowPassword] = useState(false);
  const [showReEnterPassword, setShowReEnterPassword] = useState(false);

  // Handle input changes
  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prevData => ({
      ...prevData,
      [name]: value,
    }));
  };

  // Handle form submission (placeholder)
  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    console.log('Registration Data:', formData);
    // In a real application, you would send this data to an API
  };

  // List of countries
  const countries = [
    'Select your country of residence',
    'United States',
    'Canada',
    'India',
    'United Kingdom',
    'Australia',
    'Germany',
    'France',
    'Japan',
    'China',
    'Brazil',
    'Russia',
    'Mexico',
    'Italy',
    'Spain',
    'South Korea',
    'Singapore',
    'United Arab Emirates',
    'Saudi Arabia',
    'South Africa',
  ];

  return (
    <div className="min-h-screen flex flex-col lg:flex-row font-sans">
      {/* Left panel with branding and purple gradient - Hidden on mobile */}
      <div className="hidden lg:flex lg:flex-[0_0_45%] bg-gradient-to-b from-[#1D1F8E] to-[#3d024f] text-white p-8 lg:p-16 xl:p-20 flex-col justify-center items-center relative overflow-hidden">
        <div className="flex flex-col items-center mb-20 justify-center text-center w-full max-w-md">
       
  <div className="slogan">
    <h1 className="text-4xl font-bold tracking-wide">BRILLIANCE</h1>
    <h1 className="text-4xl font-bold tracking-wide mt-2">INITIATED</h1>
  </div>

        </div>
      </div>

      {/* Mobile Header - Only shown on mobile */}
      <div className="lg:hidden bg-gradient-to-b from-[#1D1F8E] h-42 to-[#3d024f] text-white py-6 px-4 flex flex-col items-center justify-center">
      
        <div className="text-center">
          <h1 className="text-xl font-light tracking-[0.25em] uppercase leading-tight">
            BRILLIANCE
          </h1>
          <h1 className="text-xl font-light tracking-[0.25em] uppercase leading-tight">
            INITIATED
          </h1>
        </div>
      </div>

      {/* Right panel with the registration form */}
      <div className="flex-1 flex flex-col justify-center p-4 sm:p-6 md:p-8 lg:p-12 xl:p-20 bg-white">
        <div className="w-full max-w-md sm:max-w-lg md:max-w-2xl mx-auto">
          <div className="mb-6 md:mb-8">
            <h1 className="text-2xl sm:text-3xl md:text-4xl font-normal text-black mb-1">
              Register
            </h1>
            <p className="text-[#666] text-sm sm:text-base">
              Learn from the best resources.
            </p>
          </div>

          <form className="space-y-4 sm:space-y-6" onSubmit={handleSubmit}>
            {/* --- Row 1: First Name / Last Name --- */}
            <div className="flex flex-col md:flex-row gap-4 sm:gap-6">
              <div className="flex-1">
                <label htmlFor="firstName" className="block text-sm font-medium text-gray-800 mb-1 sm:mb-2">
                  First name<span className="text-red-500 ml-1">*</span>
                </label>
                <input
                  id="firstName"
                  type="text"
                  name="firstName"
                  placeholder="Enter first name"
                  value={formData.firstName}
                  onChange={handleChange}
                  required
                  className="w-full px-3 sm:px-4 py-2.5 sm:py-3.5 border border-gray-300 rounded-lg focus:border-[#174cd2] focus:ring-2 sm:focus:ring-3 focus:ring-blue-100 outline-none transition-colors text-gray-900 placeholder:text-gray-500 text-sm sm:text-base"
                />
              </div>
              <div className="flex-1">
                <label htmlFor="lastName" className="block text-sm font-medium text-gray-800 mb-1 sm:mb-2">
                  Last name<span className="text-red-500 ml-1">*</span>
                </label>
                <input
                  id="lastName"
                  type="text"
                  name="lastName"
                  placeholder="Enter last name"
                  value={formData.lastName}
                  onChange={handleChange}
                  required
                  className="w-full px-3 sm:px-4 py-2.5 sm:py-3.5 border border-gray-300 rounded-lg focus:border-[#174cd2] focus:ring-2 sm:focus:ring-3 focus:ring-blue-100 outline-none transition-colors text-gray-900 placeholder:text-gray-500 text-sm sm:text-base"
                />
              </div>
            </div>

            {/* --- Row 2: Email / Username --- */}
            <div className="flex flex-col md:flex-row gap-4 sm:gap-6">
              <div className="flex-1">
                <label htmlFor="email" className="block text-sm font-medium text-gray-800 mb-1 sm:mb-2">
                  Email<span className="text-red-500 ml-1">*</span>
                </label>
                <input
                  id="email"
                  type="email"
                  name="email"
                  placeholder="Enter email"
                  value={formData.email}
                  onChange={handleChange}
                  required
                  className="w-full px-3 sm:px-4 py-2.5 sm:py-3.5 border border-gray-300 rounded-lg focus:border-[#174cd2] focus:ring-2 sm:focus:ring-3 focus:ring-blue-100 outline-none transition-colors text-gray-900 placeholder:text-gray-500 text-sm sm:text-base"
                />
              </div>
              <div className="flex-1">
                <label htmlFor="username" className="block text-sm font-medium text-gray-800 mb-1 sm:mb-2">
                  Username<span className="text-red-500 ml-1">*</span>
                </label>
                <input
                  id="username"
                  type="text"
                  name="username"
                  placeholder="Enter username"
                  value={formData.username}
                  onChange={handleChange}
                  required
                  className="w-full px-3 sm:px-4 py-2.5 sm:py-3.5 border border-gray-300 rounded-lg focus:border-[#174cd2] focus:ring-2 sm:focus:ring-3 focus:ring-blue-100 outline-none transition-colors text-gray-900 placeholder:text-gray-500 text-sm sm:text-base"
                />
              </div>
            </div>

            {/* --- Row 3: Profession / Phone No --- */}
            <div className="flex flex-col md:flex-row gap-4 sm:gap-6">
              <div className="flex-1">
                <label htmlFor="profession" className="block text-sm font-medium text-gray-800 mb-1 sm:mb-2">
                  Profession<span className="text-red-500 ml-1">*</span>
                </label>
                <input
                  id="profession"
                  type="text"
                  name="profession"
                  placeholder="Enter profession"
                  value={formData.profession}
                  onChange={handleChange}
                  required
                  className="w-full px-3 sm:px-4 py-2.5 sm:py-3.5 border border-gray-300 rounded-lg focus:border-[#174cd2] focus:ring-2 sm:focus:ring-3 focus:ring-blue-100 outline-none transition-colors text-gray-900 placeholder:text-gray-500 text-sm sm:text-base"
                />
              </div>
              <div className="flex-1">
                <label htmlFor="phoneNo" className="block text-sm font-medium text-gray-800 mb-1 sm:mb-2">
                  Phone No.<span className="text-red-500 ml-1">*</span>
                </label>
                <input
                  id="phoneNo"
                  type="tel"
                  name="phoneNo"
                  placeholder="Enter phone no."
                  value={formData.phoneNo}
                  onChange={handleChange}
                  required
                  className="w-full px-3 sm:px-4 py-2.5 sm:py-3.5 border border-gray-300 rounded-lg focus:border-[#174cd2] focus:ring-2 sm:focus:ring-3 focus:ring-blue-100 outline-none transition-colors text-gray-900 placeholder:text-gray-500 text-sm sm:text-base"
                />
              </div>
            </div>

            {/* --- Row 4: Password / Re-enter Password --- */}
            <div className="flex flex-col md:flex-row gap-4 sm:gap-6">
              <div className="flex-1">
                <label htmlFor="password" className="block text-sm font-medium text-gray-800 mb-1 sm:mb-2">
                  Password<span className="text-red-500 ml-1">*</span>
                </label>
                <div className="relative">
                  <input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    name="password"
                    placeholder="Enter password"
                    value={formData.password}
                    onChange={handleChange}
                    required
                    className="w-full px-3 sm:px-4 py-2.5 sm:py-3.5 border border-gray-300 rounded-lg focus:border-[#174cd2] focus:ring-2 sm:focus:ring-3 focus:ring-blue-100 outline-none transition-colors text-gray-900 placeholder:text-gray-500 text-sm sm:text-base pr-10 sm:pr-12"
                  />
                  <button
                    type="button"
                    className="absolute right-2 sm:right-3 top-1/2 transform -translate-y-1/2 text-gray-600 hover:text-gray-800 p-1 text-base sm:text-lg"
                    onClick={() => setShowPassword(!showPassword)}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? '👁️' : '🔒'}
                  </button>
                </div>
              </div>

              <div className="flex-1">
                <label htmlFor="reEnterPassword" className="block text-sm font-medium text-gray-800 mb-1 sm:mb-2">
                  Re-enter Password<span className="text-red-500 ml-1">*</span>
                </label>
                <div className="relative">
                  <input
                    id="reEnterPassword"
                    type={showReEnterPassword ? 'text' : 'password'}
                    name="reEnterPassword"
                    placeholder="Re-enter password"
                    value={formData.reEnterPassword}
                    onChange={handleChange}
                    required
                    className="w-full px-3 sm:px-4 py-2.5 sm:py-3.5 border border-gray-300 rounded-lg focus:border-[#174cd2] focus:ring-2 sm:focus:ring-3 focus:ring-blue-100 outline-none transition-colors text-gray-900 placeholder:text-gray-500 text-sm sm:text-base pr-10 sm:pr-12"
                  />
                  <button
                    type="button"
                    className="absolute right-2 sm:right-3 top-1/2 transform -translate-y-1/2 text-gray-600 hover:text-gray-800 p-1 text-base sm:text-lg"
                    onClick={() => setShowReEnterPassword(!showReEnterPassword)}
                    aria-label={showReEnterPassword ? 'Hide password' : 'Show password'}
                  >
                    {showReEnterPassword ? '👁️' : '🔒'}
                  </button>
                </div>
              </div>
            </div>

            {/* --- Row 5: Current Residence (Select) --- */}
            <div>
              <label htmlFor="country" className="block text-sm font-medium text-gray-800 mb-1 sm:mb-2">
                Your current residence<span className="text-red-500 ml-1">*</span>
              </label>
              <select
                id="country"
                name="country"
                value={formData.country}
                onChange={handleChange}
                className="w-full px-3 sm:px-4 py-2.5 sm:py-3.5 border border-gray-300 rounded-lg focus:border-[#174cd2] focus:ring-2 sm:focus:ring-3 focus:ring-blue-100 outline-none transition-colors bg-white appearance-none bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22%23666%22%3E%3Cpath%20d%3D%22M7%2010l5%205%205-5z%22%2F%3E%3C%2Fsvg%3E')] bg-no-repeat bg-[right_0.75rem_center] sm:bg-[right_1rem_center] bg-[length:1rem] sm:bg-[length:1.25rem] text-sm sm:text-base"
                required
              >
                {countries.map(country => (
                  <option
                    key={country}
                    value={country === 'Select your country of residence' ? '' : country}
                    disabled={country === 'Select your country of residence'}
                    className={`${country === 'Select your country of residence' || country === '' ? 'text-gray-500' : 'text-gray-900'}`}
                  >
                    {country}
                  </option>
                ))}
              </select>
            </div>

            {/* Register Button */}
            <button 
              type="submit" 
              className="w-full bg-[#174cd2] text-white py-3 sm:py-4 rounded-lg font-semibold text-sm sm:text-base hover:bg-[#0d3db5] transition-colors mt-2 sm:mt-4"
            >
              Register
            </button>
          </form>

          <p className="text-center text-gray-600 mt-4 sm:mt-6 text-xs sm:text-sm">
            Already have an account?{' '}
            <Link 
              to="/login" 
              className="text-[#174cd2] font-semibold hover:text-[#0d3db5] hover:underline"
            >
              Login
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default Register;